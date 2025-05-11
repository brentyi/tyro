"""Msgspec Integration

In addition to standard dataclasses, :func:`tyro.cli()` also supports
`msgspec <https://jcristharif.com/msgspec/>`_ structs.

Usage:

    python ./10_msgspec.py --help
    python ./10_msgspec.py --field1 hello
    python ./10_msgspec.py --field1 hello --field2 5
"""

import msgspec

import tyro


class Args(msgspec.Struct):
    """Description.
    This should show up in the helptext!"""

    field1: str
    """A string field."""

    field2: int = 5
    """A required integer field."""


if __name__ == "__main__":
    args = tyro.cli(Args)
    print(args)
