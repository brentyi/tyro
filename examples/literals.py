import dataclasses
import enum
from typing import Literal

import dcargs


class Color(enum.Enum):
    RED = enum.auto()
    GREEN = enum.auto()
    BLUE = enum.auto()


@dataclasses.dataclass
class Args:
    enum: Color
    restricted_enum: Literal[Color.RED, Color.GREEN]
    integer: Literal[0, 1, 2, 3]
    string: Literal["red", "green"]

    restricted_enum_with_default: Literal[Color.RED, Color.GREEN] = Color.GREEN
    integer_with_default: Literal[0, 1, 2, 3] = 3
    string_with_Default: Literal["red", "green"] = "red"


if __name__ == "__main__":
    args = dcargs.parse(Args)
    print(args)
    print()
    print(dcargs.to_yaml(args))
