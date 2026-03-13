# mypy: ignore-errors
#
# Passing a Union type directly to tyro.cli() doesn't type-check correctly in
# mypy. This will be fixed by `typing.TypeForm`: https://peps.python.org/pep-0747/
"""Nested subcommands

Unions over struct types can be nested to create hierarchical subcommand
structures. By default, nested unions wrapped in ``Annotated`` are flattened
into the parent union. To create a named subcommand group, annotate the nested
union with :func:`tyro.conf.subcommand(name=...)`.

Usage:

    # Show top-level subcommands:
    python ./06_nested_subcommands.py --help

    # The `checkout` subcommand:
    python ./06_nested_subcommands.py checkout --branch main

    # `remote` is a named group containing `push` and `pull`:
    python ./06_nested_subcommands.py remote --help
    python ./06_nested_subcommands.py remote push --remote origin --branch main
    python ./06_nested_subcommands.py remote pull --remote origin
"""

from __future__ import annotations

import dataclasses

from typing_extensions import Annotated

import tyro


@dataclasses.dataclass
class Checkout:
    """Checkout a branch."""

    branch: str


@dataclasses.dataclass
class Commit:
    """Commit changes."""

    message: str


@dataclasses.dataclass
class Push:
    """Push commits to a remote."""

    remote: str = "origin"
    branch: str = "main"


@dataclasses.dataclass
class Pull:
    """Pull commits from a remote."""

    remote: str = "origin"


Remote = Annotated[
    Push | Pull,
    tyro.conf.subcommand(name="remote", description="Remote operations."),
]

if __name__ == "__main__":
    cmd = tyro.cli(Checkout | Commit | Remote)
    print(cmd)
