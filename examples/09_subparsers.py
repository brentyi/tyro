"""Unions over nested types (classes or dataclasses) are populated using subparsers.

Usage:
`python ./09_subparsers.py --help`
`python ./09_subparsers.py commit --help`
`python ./09_subparsers.py commit --cmd.message hello --cmd.all`
`python ./09_subparsers.py checkout --help`
`python ./09_subparsers.py checkout --cmd.branch main`
"""

from __future__ import annotations

import dataclasses
from typing import Union

import dcargs


@dataclasses.dataclass(frozen=True)
class Checkout:
    """Checkout a branch."""

    branch: str


@dataclasses.dataclass(frozen=True)
class Commit:
    """Commit changes."""

    message: str
    all: bool = False


def main(cmd: Union[Checkout, Commit] = Checkout("main")) -> None:
    print(cmd)


if __name__ == "__main__":
    dcargs.cli(main)
