"""An argument parsing example.

Note that multiple possible documentation styles are supported by the field helptext
generator; we could also use docstring-style triple quote comments, or #-style comments
on the same line.
"""

import dataclasses
import enum

import dcargs


class OptimizerType(enum.Enum):
    ADAM = enum.auto()
    SGD = enum.auto()


@dataclasses.dataclass(frozen=True)
class OptimizerConfig:
    # Gradient-based optimizer to use.
    algorithm: OptimizerType = OptimizerType.ADAM

    # Learning rate to use.
    learning_rate: float = 3e-4

    # Coefficient for L2 regularization.
    weight_decay: float = 1e-2


@dataclasses.dataclass(frozen=True)
class ExperimentConfig:
    """A nested experiment configuration. Note that the argument parser description is
    pulled from this docstring by default, but can also be overrided with
    `dcargs.cli()`'s `description=` argument."""

    # Experiment name to use.
    experiment_name: str

    # Various configurable options for our optimizer.
    optimizer: OptimizerConfig

    # Random seed. This is helpful for making sure that our experiments are all
    # reproducible!
    seed: int = 0


if __name__ == "__main__":
    config = dcargs.cli(ExperimentConfig)
    print(config)
    print(dcargs.to_yaml(config))
