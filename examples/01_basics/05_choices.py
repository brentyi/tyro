"""Choices

:py:data:`typing.Literal[]` can be used to restrict inputs to a fixed set of literal choices.

Usage:

    python ./05_choices.py --help
    python ./05_choices.py --string red
    python ./05_choices.py --string blue
"""

import dataclasses
from pprint import pprint
from typing import Literal

import tyro


@dataclasses.dataclass
class Args:
    # We can use Literal[] to restrict the set of allowable inputs, for example, over
    # a set of strings.
    string: Literal["red", "green"] = "red"

    # Integers also work. (as well as booleans, enums, etc)
    number: Literal[0, 1, 2] = 0


if __name__ == "__main__":
    args = tyro.cli(Args)
    pprint(args)
