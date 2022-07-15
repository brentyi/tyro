"""We can integrate `dcargs.cli()` into common configuration patterns: here, we select
one of multiple possible base configurations, and then use the CLI to either override
(existing) or fill in (missing) values.

Usage:
`python ./06_base_configs_argv.py`
`python ./06_base_configs_argv.py small --help`
`python ./06_base_configs_argv.py small --seed 94720`
`python ./06_base_configs_argv.py big --help`
`python ./06_base_configs_argv.py big --seed 94720`
"""

import dataclasses
import sys
from typing import Dict, Literal, Tuple, Type, TypeVar, Union

import dcargs


@dataclasses.dataclass
class AdamOptimizer:
    # Adam learning rate.
    learning_rate: float = 1e-3

    # Moving average parameters.
    betas: Tuple[float, float] = (0.9, 0.999)


@dataclasses.dataclass
class SgdOptimizer:
    # SGD learning rate.
    learning_rate: float = 3e-4


@dataclasses.dataclass(frozen=True)
class ExperimentConfig:
    # Dataset to run experiment on.
    dataset: Literal["mnist", "imagenet-50"]

    # Optimizer parameters.
    optimizer: Union[AdamOptimizer, SgdOptimizer]

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


# Note that we could also define this library using separate YAML files (similar to
# `config_path`/`config_name` in Hydra), but staying in Python enables seamless type
# checking + IDE support.
base_config_library = {
    "small": ExperimentConfig(
        dataset="mnist",
        optimizer=SgdOptimizer(),
        batch_size=2048,
        num_layers=4,
        units=64,
        train_steps=30_000,
        # The dcargs.MISSING sentinel allows us to specify that the seed should have no
        # default, and needs to be populated from the CLI.
        seed=dcargs.MISSING,
    ),
    "big": ExperimentConfig(
        dataset="imagenet-50",
        optimizer=AdamOptimizer(),
        batch_size=32,
        num_layers=8,
        units=256,
        train_steps=100_000,
        seed=dcargs.MISSING,
    ),
}


T = TypeVar("T")


def cli_with_base_configs(cls: Type[T], base_library: Dict[str, T]) -> T:
    # Get base configuration name from the first positional argument.
    if len(sys.argv) < 2 or sys.argv[1] not in base_library:
        valid_usages = map(lambda k: f"{sys.argv[0]} {k} --help", base_library.keys())
        raise SystemExit("usage:\n  " + "\n  ".join(valid_usages))

    # Get base configuration from our library, and use it for default CLI parameters.
    default_instance = base_library[sys.argv[1]]
    return dcargs.cli(
        cls,
        prog=" ".join(sys.argv[:2]),
        args=sys.argv[2:],
        default_instance=default_instance,
        # `avoid_subparsers` will avoid making a subparser for unions when a default is
        # provided; in this case, it simplifies our CLI but makes it less expressive
        # (cannot switch away from the base optimizer types).
        avoid_subparsers=True,
    )


if __name__ == "__main__":
    config = cli_with_base_configs(ExperimentConfig, base_config_library)
    print(config)
