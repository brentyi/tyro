"""An argument parsing example.

Note that there are multiple possible ways to document dataclass attributes, all
of which are supported by the automatic helptext generator.
"""

import dataclasses
import enum

import dcargs


class OptimizerType(enum.Enum):
    ADAM = enum.auto()
    SGD = enum.auto()


@dataclasses.dataclass(frozen=True)
class OptimizerConfig:
    # Variant of SGD to use.
    type: OptimizerType

    # Learning rate to use.
    learning_rate: float = 3e-4

    # Coefficient for L2 regularization.
    weight_decay: float = 1e-2


@dataclasses.dataclass(frozen=True)
class ExperimentConfig:
    """A nested experiment configuration. Note that the argument parser description is
    pulled from this docstring by default, but can also be overrided with
    `dcargs.parse`'s `description=` flag."""

    experiment_name: str  # Experiment name to use.

    optimizer: OptimizerConfig

    seed: int = 0
    """Random seed. This is helpful for making sure that our experiments are
    all reproducible!"""


if __name__ == "__main__":
    config = dcargs.parse(ExperimentConfig)
    print(config)
    print(dcargs.to_yaml(config))
