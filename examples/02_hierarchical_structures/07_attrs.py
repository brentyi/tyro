"""Attrs Integration

In addition to standard dataclasses, :func:`tyro.cli()` also supports
`attrs <https://www.attrs.org/>`_ classes.

Usage:

    python ./07_attrs.py --help
    python ./07_attrs.py --field1 hello
    python ./07_attrs.py --field1 hello --field2 5
"""

import attr

import tyro


@attr.s
class Args:
    """Description.
    This should show up in the helptext!"""

    field1: str = attr.ib()
    """A string field."""

    field2: int = attr.ib(factory=lambda: 5)
    """A required integer field."""


if __name__ == "__main__":
    args = tyro.cli(Args)
    print(args)
