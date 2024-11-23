"""Unions

:code:`X | Y` or :py:data:`typing.Union` can be used to expand inputs to
multiple types.

Usage:

    python ./07_unions.py --help
    python ./07_unions.py --union-over-types 3
    python ./07_unions.py --union-over-types three
    python ./07_unions.py --integer None
    python ./07_unions.py --integer 0
"""

import dataclasses
import enum
from pprint import pprint
from typing import Literal, Optional

import tyro


class Color(enum.Enum):
    RED = enum.auto()
    GREEN = enum.auto()
    BLUE = enum.auto()


@dataclasses.dataclass
class Args:
    # Unions can be used to specify multiple allowable types.
    union_over_types: int | str = 0
    string_or_enum: Literal["red", "green"] | Color = "red"

    # Unions also work over more complex nested types.
    union_over_tuples: tuple[int, int] | tuple[str] = ("1",)

    # And can be nested in other types.
    tuple_of_string_or_enum: tuple[Literal["red", "green"] | Color, ...] = (
        "red",
        Color.RED,
    )

    # Optional[T] is equivalent to `T | None`.
    integer: Optional[Literal[0, 1, 2, 3]] = None


if __name__ == "__main__":
    args = tyro.cli(Args)
    pprint(args)
