"""Multi-value Arguments

Arguments of both fixed and variable lengths can be annotated with standard Python
collection types: `typing.List[T]`, `typing.Tuple[T1, T2]`, etc. In Python >=3.9,
`list[T]` and `tuple[T]` are also supported.

Usage:
`python ./03_collections.py --help`
`python ./03_collections.py --dataset-sources ./data --image-dimensions 16 16`
`python ./03_collections.py --dataset-sources ./data`
"""

import dataclasses
import pathlib
from typing import Tuple

import tyro


@dataclasses.dataclass(frozen=True)
class TrainConfig:
    # Example of a variable-length tuple. `typing.List`, `typing.Sequence`,
    # `typing.Set`, `typing.Dict`, etc are all supported as well.
    dataset_sources: Tuple[pathlib.Path, ...]
    """Paths to load training data from. This can be multiple!"""

    # Fixed-length tuples are also okay.
    image_dimensions: Tuple[int, int] = (32, 32)
    """Height and width of some image data."""


if __name__ == "__main__":
    config = tyro.cli(TrainConfig)
    print(config)
