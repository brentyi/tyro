"""Dataclasses

Common pattern: use :func:`tyro.cli()` to instantiate a dataclass.

Usage:
`python ./02_dataclasses.py --help`
`python ./02_dataclasses.py --field1 hello`
`python ./02_dataclasses.py --field1 hello --field2 5`
"""

import dataclasses

import tyro


@dataclasses.dataclass
class Args:
    """Description.
    This should show up in the helptext!"""

    field1: str
    """A string field."""

    field2: int = 3
    """A numeric field, with a default value."""


if __name__ == "__main__":
    args = tyro.cli(Args)
    print(args)
