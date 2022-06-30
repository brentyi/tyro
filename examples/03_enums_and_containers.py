"""Examples of more advanced type annotations: enums and containers types.

For collections, we only showcase Tuple here, but List, Sequence, Set, etc are all
supported as well."""

import dataclasses
import enum
import pathlib
from typing import Optional, Tuple

import dcargs


class OptimizerType(enum.Enum):
    ADAM = enum.auto()
    SGD = enum.auto()


@dataclasses.dataclass(frozen=True)
class TrainConfig:
    # Example of a variable-length tuple:
    dataset_sources: Tuple[pathlib.Path, ...]
    """Paths to load training data from. This can be multiple!"""

    # Fixed-length tuples are also okay:
    image_dimensions: Tuple[int, int]
    """Height and width of some image data."""

    # Enums are handled seamlessly.
    optimizer_type: OptimizerType
    """Gradient-based optimizer to use."""

    # We can also explicitly mark arguments as optional.
    checkpoint_interval: Optional[int]
    """Interval to save checkpoints at."""


if __name__ == "__main__":
    config = dcargs.cli(TrainConfig)
    print(config)
