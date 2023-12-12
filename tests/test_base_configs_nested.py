from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Tuple

from torch import nn
from typing_extensions import Literal

import tyro


@dataclass(frozen=True)
class AdamOptimizer:
    learning_rate: float = 1e-3
    betas: Tuple[float, float] = (0.9, 0.999)


@dataclass(frozen=True)
class SGDOptimizer:
    learning_rate: float = 1e-3
    momentum: float = 0.9


@dataclass(frozen=True)
class DataConfig:
    test: int = 0


@dataclass(frozen=True)
class ExperimentConfig:
    # Dataset to run experiment on.
    dataset: Literal["mnist", "imagenet-50"]

    # Optimizer parameters.
    optimizer: AdamOptimizer

    # Model size.
    num_layers: int
    units: int

    # Batch size.
    batch_size: int

    # Total number of training steps.
    train_steps: int

    # Random seed. This is helpful for making sure that our experiments are all
    # reproducible!
    seed: int

    # Activation to use. Not specifiable via the commandline.
    activation: Callable[[], nn.Module]


DataConfigDataParserUnion = tyro.extras.subcommand_type_from_defaults(
    {
        "small-data": DataConfig(
            test=2221,
        ),
        "big-data": DataConfig(
            test=2,
        ),
    },
    prefix_names=False,  # Omit prefixes in subcommands themselves.
)


# Note that we could also define this library using separate YAML files (similar to
# `config_path`/`config_name` in Hydra), but staying in Python enables seamless type
# checking + IDE support.
ExperimentConfigDataParserUnion = tyro.extras.subcommand_type_from_defaults(
    {
        "small": ExperimentConfig(
            dataset="mnist",
            optimizer=AdamOptimizer(),
            batch_size=2048,
            num_layers=4,
            units=64,
            train_steps=30_000,
            seed=0,
            activation=nn.ReLU,
        ),
        "big": ExperimentConfig(
            dataset="imagenet-50",
            optimizer=AdamOptimizer(),
            batch_size=32,
            num_layers=8,
            units=256,
            train_steps=100_000,
            seed=0,
            activation=nn.GELU,
        ),
    },
    prefix_names=False,  # Omit prefixes in subcommands themselves.
)


if TYPE_CHECKING:
    AnnotatedDataParserUnion = DataConfig
    AnnotatedExperimentParserUnion = ExperimentConfig
else:
    AnnotatedDataParserUnion = tyro.conf.OmitSubcommandPrefixes[
        DataConfigDataParserUnion
    ]  # Omit prefixes of flags in subcommands.
    AnnotatedExperimentParserUnion = tyro.conf.OmitSubcommandPrefixes[
        ExperimentConfigDataParserUnion
    ]  # Omit prefixes of flags in subcommands.


@dataclass
class BaseConfig:
    # The name of the experiment to run.
    experiment: str

    # The path to the output directory.
    output_dir: str

    # The experiment configuration.
    experiment_config: AnnotatedExperimentParserUnion

    # The experiment configuration.
    data_config: AnnotatedDataParserUnion = DataConfig()


def test_base_configs_nested() -> None:
    def main(cfg: BaseConfig) -> BaseConfig:
        return cfg

    assert tyro.cli(
        main,
        args="--cfg.experiment test --cfg.output-dir test small".split(" "),
    ) == BaseConfig(
        "test",
        "test",
        ExperimentConfig(
            dataset="mnist",
            optimizer=AdamOptimizer(),
            batch_size=2048,
            num_layers=4,
            units=64,
            train_steps=30_000,
            seed=0,
            activation=nn.ReLU,
        ),
        DataConfig(0),
    )
    assert tyro.cli(
        main,
        args="--cfg.experiment test --cfg.output-dir test small small-data".split(" "),
    ) == BaseConfig(
        "test",
        "test",
        ExperimentConfig(
            dataset="mnist",
            optimizer=AdamOptimizer(),
            batch_size=2048,
            num_layers=4,
            units=64,
            train_steps=30_000,
            seed=0,
            activation=nn.ReLU,
        ),
        DataConfig(2221),
    )
    assert tyro.cli(
        main,
        args="--cfg.experiment test --cfg.output-dir test small big-data".split(" "),
    ) == BaseConfig(
        "test",
        "test",
        ExperimentConfig(
            dataset="mnist",
            optimizer=AdamOptimizer(),
            batch_size=2048,
            num_layers=4,
            units=64,
            train_steps=30_000,
            seed=0,
            activation=nn.ReLU,
        ),
        DataConfig(2),
    )
