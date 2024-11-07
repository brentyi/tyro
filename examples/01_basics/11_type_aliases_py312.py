# mypy: ignore-errors
#
# PEP 695 isn't yet supported in mypy. (April 4, 2024)
"""Type Aliases (3.12+)

In Python 3.12, the :code:`type` statement is introduced to create type aliases.

Usage:

    python ./11_type_aliases_py312.py --help
"""

import dataclasses

import tyro

# Lazily-evaluated type alias.
type Field1Type = Inner


@dataclasses.dataclass
class Inner:
    a: int
    b: str


@dataclasses.dataclass
class Args:
    """Description.
    This should show up in the helptext!"""

    field1: Field1Type
    """A field."""

    field2: int = 3
    """A numeric field, with a default value."""


if __name__ == "__main__":
    args = tyro.cli(Args)
    print(args)
