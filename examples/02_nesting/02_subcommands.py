"""Subcommands

Unions over nested types (classes or dataclasses) are populated using subcommands.

For configuring subcommands beyond what can be expressed with type annotations, see
:func:`tyro.conf.subcommand()`.

Usage:
`python ./02_subcommands.py --help`
`python ./02_subcommands.py cmd:commit --help`
`python ./02_subcommands.py cmd:commit --cmd.message hello --cmd.all`
`python ./02_subcommands.py cmd:checkout --help`
`python ./02_subcommands.py cmd:checkout --cmd.branch main`
"""

from __future__ import annotations

import dataclasses
from typing import Union

import tyro


@dataclasses.dataclass(frozen=True)
class Checkout:
    """Checkout a branch."""

    branch: str


@dataclasses.dataclass(frozen=True)
class Commit:
    """Commit changes."""

    message: str
    all: bool = False


def main(cmd: Union[Checkout, Commit]) -> None:
    print(cmd)


if __name__ == "__main__":
    # Note that we can also pass `Union[Checkout, Command]` directly into
    # `tyro.cli()`; this is understood by tyro and pyright, but unfortunately not by
    # mypy.
    tyro.cli(main)
