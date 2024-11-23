"""Choosing Base Configs

One common pattern is to have a set of "base" configurations, which can be
selected from and then overridden.

This is often implemented with a set of configuration files (e.g., YAML files).
With :mod:`tyro`, we can instead define each base configuration as a separate
Python object.

After creating the base configurations, we can use the CLI to select one of
them and then override (existing) or fill in (missing) values.

The helper function used here, :func:`tyro.extras.overridable_config_cli()`, is
a lightweight wrapper over :func:`tyro.cli()` and its Union-based subcommand
syntax.


Usage:

    # Overall helptext:
    python ./03_choosing_base_configs.py --help

    # The "small" subcommand:
    python ./03_choosing_base_configs.py small --help
    python ./03_choosing_base_configs.py small --seed 94720

    # The "big" subcommand:
    python ./03_choosing_base_configs.py big --help
    python ./03_choosing_base_configs.py big --seed 94720
"""

from dataclasses import dataclass
from typing import Callable, Literal

from torch import nn

import tyro


@dataclass
class ExperimentConfig:
    # Dataset to run experiment on.
    dataset: Literal["mnist", "imagenet-50"]

    # Model size.
    num_layers: int
    units: int

    # Batch size.
    batch_size: int

    # Total number of training steps.
    train_steps: int

    # Random seed.
    seed: int

    # Not specifiable via the commandline.
    activation: Callable[[], nn.Module]


# We could also define this library using separate YAML files (similar to
# `config_path`/`config_name` in Hydra), but staying in Python enables seamless
# type checking + IDE support.
default_configs = {
    "small": (
        "Small experiment.",
        ExperimentConfig(
            dataset="mnist",
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
