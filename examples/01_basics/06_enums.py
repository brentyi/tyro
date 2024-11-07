"""Enums

In addition to literals, enums can also be used to provide a fixed set of
choices.

Usage:

    python ./06_enums.py --help
    python ./06_enums.py --color RED
    python ./06_enums.py --color BLUE --opacity 0.75
"""

import enum
from dataclasses import dataclass
from pprint import pprint

import tyro


class Color(enum.Enum):
    RED = enum.auto()
    BLUE = enum.auto()


@dataclass
class Config:
    color: Color = Color.RED
    """Color argument."""

    opacity: float = 0.5
    """Opacity argument."""


if __name__ == "__main__":
    config = tyro.cli(Config)
    pprint(config)
