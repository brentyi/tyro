"""Choices

`typing.Literal[]` can be used to restrict inputs to a fixed set of literal choices.

Usage:
`python ./06_literals.py --help`
"""

import dataclasses
import enum
from typing import Literal

import tyro


class Color(enum.Enum):
    RED = enum.auto()
    GREEN = enum.auto()
    BLUE = enum.auto()


@dataclasses.dataclass(frozen=True)
class Args:
    # We can use Literal[] to restrict the set of allowable inputs, for example, over
    # a set of strings.
    strings: Literal["red", "green"] = "red"

    # Enums also work.
    enums: Literal[Color.RED, Color.GREEN] = Color.RED

    # Or mix them with other types!
    mixed: Literal[Color.RED, Color.GREEN, "blue"] = "blue"


if __name__ == "__main__":
    args = tyro.cli(Args)
    print(args)
