# mypy: ignore-errors
#
# Passing a Union type directly to tyro.cli() doesn't type-check correctly in
# mypy. This will be fixed by `typing.TypeForm`: https://peps.python.org/pep-0747/
"""Subcommands are Unions

All of :mod:`tyro`'s subcommand features are built using unions over struct
types (typically dataclasses). Subcommands are used to choose between types in
the union; arguments are then populated from the chosen type.

.. note::

    For configuring subcommands beyond what can be expressed with type annotations, see
    :func:`tyro.conf.subcommand()`.

Usage:

    # Print the helptext. This will show the available subcommands:
    python ./01_subcommands.py --help

    # The `commit` subcommand:
    python ./01_subcommands.py commit --help
    python ./01_subcommands.py commit --message hello

    # The `checkout` subcommand:
    python ./01_subcommands.py checkout --help
    python ./01_subcommands.py checkout --branch main
"""

from __future__ import annotations

import dataclasses

import tyro


@dataclasses.dataclass
class Checkout:
    """Checkout a branch."""

    branch: str


@dataclasses.dataclass
class Commit:
    """Commit changes."""

    message: str


if __name__ == "__main__":
    cmd = tyro.cli(Checkout | Commit)
    print(cmd)
