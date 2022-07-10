"""Example using `dcargs.cli()` to instantiate a named tuple.

Usage:
`python ./12_named_tuples.py --help`
`python ./12_named_tuples.py --field1 hello`
"""

from typing import NamedTuple

import dcargs


class TupleType(NamedTuple):
    """Description.
    This should show up in the helptext!"""

    field1: str  # A string field.
    field2: int = 3  # A numeric field, with a default value.
    flag: bool = False  # A boolean flag.


if __name__ == "__main__":
    x = dcargs.cli(TupleType)
    assert isinstance(x, tuple)
    print(x)
