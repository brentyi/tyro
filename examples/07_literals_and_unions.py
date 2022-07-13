"""`typing.Literal[]` can be used to restrict inputs to a fixed set of literal choices;
`typing.Union[]` can be used to restrict inputs to a fixed set of types.

Usage:
`python ./07_literals_and_unions.py --help`
`python ./07_literals_and_unions.py --enum RED --restricted-enum GREEN --integer 3 --string green`
`python ./07_literals_and_unions.py --string-or-enum green`
`python ./07_literals_and_unions.py --string-or-enum RED`
`python ./07_literals_and_unions.py --tuple-of-string-or-enum RED green BLUE`
"""

import dataclasses
import enum
from typing import Literal, Tuple, Union

import dcargs


class Color(enum.Enum):
    RED = enum.auto()
    GREEN = enum.auto()
    BLUE = enum.auto()


@dataclasses.dataclass(frozen=True)
class Args:
    enum: Color = Color.RED
    restricted_enum: Literal[Color.RED, Color.GREEN] = Color.RED
    integer: Literal[0, 1, 2, 3] = 0
    string: Literal["red", "green"] = "red"
    string_or_enum: Union[Literal["red", "green"], Color] = "red"
    tuple_of_string_or_enum: Tuple[Union[Literal["red", "green"], Color], ...] = (
        "red",
        Color.RED,
    )


if __name__ == "__main__":
    args = dcargs.cli(Args)
    print(args)
