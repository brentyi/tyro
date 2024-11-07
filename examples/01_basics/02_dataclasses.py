"""Dataclasses

In addition to functions, :func:`tyro.cli()` can also take dataclasses as input.

Usage:

    # To show the help message, we can use the ``--help`` flag:
    python ./02_dataclasses.py --help

    # We can override ``field1`` and ``field2``:
    python ./02_dataclasses.py --field1 hello
    python ./02_dataclasses.py --field1 hello --field2 5
"""

from dataclasses import dataclass
from pprint import pprint

import tyro


@dataclass
class Args:
    """Description.
    This should show up in the helptext!"""

    field1: str
    """A string field."""

    field2: int = 3
    """A numeric field, with a default value."""


if __name__ == "__main__":
    args = tyro.cli(Args)
    pprint(args)
