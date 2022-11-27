"""Nesting in Containers

Structures can be nested inside of standard containers.

Note that lengths must be inferable, either via a fixed-length tuple annotation or by
parsing default values.


Usage:
`python ./04_nesting_in_containers.py.py --help`
"""
import dataclasses
from typing import Dict, Tuple

import tyro


class Color:
    pass


@dataclasses.dataclass
class RGB(Color):
    r: int
    g: int
    b: int


@dataclasses.dataclass
class HSL(Color):
    h: int
    s: int
    l: int


@dataclasses.dataclass
class Args:
    # Example of specifying nested structures via a fixed-length tuple.
    color_tuple: Tuple[RGB, HSL]

    # Examples of nested structures in variable-length containers. These need a default
    # provided for length inference; we don't currently support specifying dynamic
    # container lengths directly from the commandline.
    color_tuple_alt: Tuple[Color, ...] = (
        RGB(255, 0, 0),
        HSL(0, 255, 0),
    )
    color_map: Dict[str, RGB] = dataclasses.field(
        # We can't use mutable values as defaults directly.
        default_factory={
            "red": RGB(255, 0, 0),
            "green": RGB(0, 255, 0),
            "blue": RGB(0, 0, 255),
        }.copy
    )


if __name__ == "__main__":
    args = tyro.cli(Args)
    print(args)
