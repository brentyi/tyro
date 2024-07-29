"""Choices

:code:`typing.Literal[]` can be used to restrict inputs to a fixed set of literal choices.

Usage:
`python ./06_literals.py --help`
"""

import dataclasses
from typing import Literal

import tyro


@dataclasses.dataclass(frozen=True)
class Args:
    # We can use Literal[] to restrict the set of allowable inputs, for example, over
    # a set of strings.
    strings: Literal["red", "green"] = "red"

    # Integers also work. (as well as booleans, enums, etc)
    numbers: Literal[0, 1, 2] = 0


if __name__ == "__main__":
    args = tyro.cli(Args)
    print(args)
