"""Example using `dcargs.cli()` to instantiate tuple types.

Usage:
`python ./12_tuples.py --help`
`python ./12_tuples.py --color 127 127 127`
`python ./12_tuples.py --two_colors[1].r 127 --two_colors[1].g 0 --two_colors[1].b 0`
"""

import dataclasses
from typing import NamedTuple, Tuple

import dcargs


@dataclasses.dataclass
class Color:
    r: int
    g: int
    b: int


class TupleType(NamedTuple):
    """Description.
    This should show up in the helptext!"""

    # Tuple types can contain raw values.
    color: Tuple[int, int, int] = (255, 0, 0)

    # Tuple types can contain nested structures.
    two_colors: Tuple[Color, Color] = (Color(255, 0, 0), Color(0, 255, 0))


if __name__ == "__main__":
    x = dcargs.cli(TupleType)
    assert isinstance(x, tuple)
    print(x)
