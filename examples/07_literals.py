"""`typing.Literal[]` can be used to restrict inputs to a fixed set of choices.

Usage:
`python ./07_literals.py --help`
`python ./07_literals.py --enum RED --restricted-enum GREEN --integer 3 --string green`
"""

import dataclasses
import enum
from typing import Literal

import dcargs


class Color(enum.Enum):
    RED = enum.auto()
    GREEN = enum.auto()
    BLUE = enum.auto()


@dataclasses.dataclass(frozen=True)
class Args:
    enum: Color
    restricted_enum: Literal[Color.RED, Color.GREEN]

    integer: Literal[0, 1, 2, 3]
    string: Literal["red", "green"]

    restricted_enum_with_default: Literal[Color.RED, Color.GREEN] = Color.GREEN
    integer_with_default: Literal[0, 1, 2, 3] = 3
    string_with_Default: Literal["red", "green"] = "red"


if __name__ == "__main__":
    args = dcargs.cli(Args)
    print(args)
