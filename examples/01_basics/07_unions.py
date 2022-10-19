"""Unions

`typing.Union[]` can be used to expand inputs to multiple types.

Usage:
`python ./07_unions.py --help`
"""

import dataclasses
import enum
from typing import Literal, Optional, Tuple, Union

import tyro


class Color(enum.Enum):
    RED = enum.auto()
    GREEN = enum.auto()
    BLUE = enum.auto()


@dataclasses.dataclass(frozen=True)
class Args:
    # Unions can be used to specify multiple allowable types.
    union_over_types: Union[int, str] = 0
    string_or_enum: Union[Literal["red", "green"], Color] = "red"

    # Unions also work over more complex nested types.
    union_over_tuples: Union[Tuple[int, int], Tuple[str]] = ("1",)

    # And can be nested in other types.
    tuple_of_string_or_enum: Tuple[Union[Literal["red", "green"], Color], ...] = (
        "red",
        Color.RED,
    )

    # Optional[T] is equivalent to Union[T, None].
    integer: Optional[Literal[0, 1, 2, 3]] = None


if __name__ == "__main__":
    args = tyro.cli(Args)
    print(args)
