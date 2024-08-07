"""Multi-value Arguments

Arguments of both fixed and variable lengths can be annotated with standard
Python collection types. For Python 3.7 and 3.8, we can use either :code:`from
__future__ import annotations` to support :code:`list[T]` and :code:`tuple[T]`,
or the older API :code:`typing.List[T]` and :code:`typing.Tuple[T1, T2]`.

Usage:
`python ./03_collections.py --help`
`python ./03_collections.py --dataset-sources ./data --image-dimensions 16 16`
`python ./03_collections.py --dataset-sources ./data`
"""

import dataclasses
import pathlib

import tyro


@dataclasses.dataclass(frozen=True)
class TrainConfig:
    # Example of a variable-length tuple. `list[T]`, `set[T]`,
    # `dict[K, V]`, etc are supported as well.
    dataset_sources: tuple[pathlib.Path, ...]
    """Paths to load training data from. This can be multiple!"""

    # Fixed-length tuples are also okay.
    image_dimensions: tuple[int, int] = (32, 32)
    """Height and width of some image data."""


if __name__ == "__main__":
    config = tyro.cli(TrainConfig)
    print(config)
