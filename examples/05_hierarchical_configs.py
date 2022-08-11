"""Structures (typically dataclasses) can be nested to build hierarchical configuration
objects. This helps with modularity and grouping in larger projects.

Usage:
`python ./05_hierarchical_configs.py --help`
`python ./05_hierarchical_configs.py --out-dir . --config.optimizer.algorithm SGD`
`python ./05_hierarchical_configs.py --out-dir . --restore-checkpoint`
"""

import dataclasses
import enum
import pathlib
from typing import Tuple

import dcargs


class OptimizerType(enum.Enum):
    ADAM = enum.auto()
    SGD = enum.auto()


@dataclasses.dataclass
class OptimizerConfig:
    # Gradient-based optimizer to use.
    algorithm: OptimizerType = OptimizerType.ADAM

    # Learning rate to use.
    learning_rate: float = 3e-4

    # Coefficient for L2 regularization.
    weight_decay: float = 1e-2


@dataclasses.dataclass
class ExperimentConfig:
    # Various configurable options for our optimizer.
    optimizer: Tuple[OptimizerConfig, OptimizerConfig, OptimizerConfig]

    # Batch size.
    batch_size: int = 32

    # Total number of training steps.
    train_steps: int = 100_000

    # Random seed. This is helpful for making sure that our experiments are all
    # reproducible!
    seed: int = 0


def train(
    out_dir: pathlib.Path,
    config: ExperimentConfig,
    restore_checkpoint: bool = False,
    checkpoint_interval: int = 1000,
) -> None:
    """Train a model.

    Args:
        out_dir: Where to save logs and checkpoints.
        config: Experiment configuration.
        restore_checkpoint: Set to restore an existing checkpoint.
        checkpoint_interval: Training steps between each checkpoint save.
    """
    print(f"{out_dir=}, {restore_checkpoint=}, {checkpoint_interval=}")
    print()
    print(f"{config=}")
    print()
    print(dcargs.to_yaml(config))


if __name__ == "__main__":
    dcargs.cli(train)
