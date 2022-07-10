"""We can generate argument parsers from more advanced type annotations, like enums and
tuple types. For collections, we only showcase `Tuple` here, but `List`, `Sequence`,
`Set`, `Dict`, etc are all supported as well.

Usage:
`python ./03_enums_and_containers.py --help`
`python ./03_enums_and_containers.py --dataset-sources ./data --image-dimensions 16 16`
`python ./03_enums_and_containers.py --dataset-sources ./data --optimizer-type SGD`
"""

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
    image_dimensions: Tuple[int, int] = (32, 32)
    """Height and width of some image data."""

    # Enums are handled seamlessly.
    optimizer_type: OptimizerType = OptimizerType.ADAM
    """Gradient-based optimizer to use."""

    # We can also explicitly mark arguments as optional.
    checkpoint_interval: Optional[int] = None
    """Interval to save checkpoints at."""


if __name__ == "__main__":
    config = dcargs.cli(TrainConfig)
    print(config)
