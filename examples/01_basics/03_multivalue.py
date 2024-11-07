"""Multi-value Arguments

Arguments of both fixed and variable lengths can be annotated with standard
Python collection types. For Python 3.7 and 3.8, we can use either ``from
__future__ import annotations`` to support ``list[T]`` and ``tuple[T]``,
or the older :py:class:`typing.List` and :py:data:`typing.Tuple`.

Usage:

    # To print help:
    python ./03_multivalue.py --help

    # We can override arguments:
    python ./03_multivalue.py --source-paths ./data --dimensions 16 16
    python ./03_multivalue.py --source-paths ./data1 ./data2
"""

import pathlib
from dataclasses import dataclass
from pprint import pprint

import tyro


@dataclass
class Config:
    # Example of a variable-length tuple. `list[T]`, `set[T]`,
    # `dict[K, V]`, etc are supported as well.
    source_paths: tuple[pathlib.Path, ...]
    """This can be multiple!"""

    # Fixed-length tuples are also okay.
    dimensions: tuple[int, int] = (32, 32)
    """Height and width."""


if __name__ == "__main__":
    config = tyro.cli(Config)
    pprint(config)
