"""Tuples and NamedTuple

Example using :func:`tyro.cli()` to instantiate tuple types. :py:class:`tuple`,
:py:data:`typing.Tuple`, and :py:class:`typing.NamedTuple` are all supported.

Usage:

    python ./05_tuples.py --help
    python ./05_tuples.py --color 127 127 127
    python ./05_tuples.py --two-colors.1.r 127 --two-colors.1.g 0 --two-colors.1.b 0
"""

from typing import NamedTuple

import tyro


# Named tuples are interpreted as nested structures.
class Color(NamedTuple):
    r: int
    g: int
    b: int


class TupleType(NamedTuple):
    """Description.
    This should show up in the helptext!"""

    # Tuple types can contain raw values.
    color: tuple[int, int, int] = (255, 0, 0)

    # Tuple types can contain nested structures.
    two_colors: tuple[Color, Color] = (Color(255, 0, 0), Color(0, 255, 0))


if __name__ == "__main__":
    x = tyro.cli(TupleType)
    assert isinstance(x, tuple)
    print(x)
