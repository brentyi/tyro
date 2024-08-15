"""Base Configurations

We can integrate `tyro` into common configuration patterns: here, we select
one of multiple possible base configurations, create a subcommand for each one, and then
use the CLI to either override (existing) or fill in (missing) values.

The helper function used here, :func:`tyro.extras.overridable_config_cli()`, is a
lightweight wrapper over :func:`tyro.cli()`.


Usage:
`python ./01_base_configs.py --help`
`python ./01_base_configs.py small --help`
`python ./01_base_configs.py small --seed 94720`
`python ./01_base_configs.py big --help`
`python ./01_base_configs.py big --seed 94720`
"""

from dataclasses import dataclass
from typing import Callable, Literal

from torch import nn

import tyro


@dataclass(frozen=True)
class AdamOptimizer:
    learning_rate: float = 1e-3
    betas: tuple[float, float] = (0.9, 0.999)


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


# Note that we could also define this library using separate YAML files (similar to
# `config_path`/`config_name` in Hydra), but staying in Python enables seamless type
# checking + IDE support.
default_configs = {
    "small": (
        "Small experiment.",
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
    ),
    "big": (
        "Big experiment.",
        ExperimentConfig(
            dataset="imagenet-50",
            optimizer=AdamOptimizer(),
            batch_size=32,
            num_layers=8,
            units=256,
            train_steps=100_000,
            seed=0,
            activation=nn.GELU,
        ),
    ),
}
if __name__ == "__main__":
    config = tyro.extras.overridable_config_cli(default_configs)
    print(config)
