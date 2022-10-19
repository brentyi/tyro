"""Enums

We can generate argument parsers from more advanced type annotations, like enums.

Usage:
`python ./04_enums.py --help`
`python ./04_enums.py --optimizer-type SGD`
`python ./04_enums.py --optimizer-type ADAM --learning-rate 3e-4`
"""

import dataclasses
import enum

import tyro


class OptimizerType(enum.Enum):
    ADAM = enum.auto()
    SGD = enum.auto()


@dataclasses.dataclass(frozen=True)
class TrainConfig:
    # Enums are handled seamlessly.
    optimizer_type: OptimizerType = OptimizerType.ADAM
    """Gradient-based optimizer to use."""

    learning_rate: float = 1e-4
    """Learning rate for optimizer."""


if __name__ == "__main__":
    config = tyro.cli(TrainConfig)
    print(config)
