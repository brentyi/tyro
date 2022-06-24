"""Unions over nested types (classes or dataclasses) will result in subparsers."""

from __future__ import annotations

import dataclasses
from typing import Union

import dcargs


def main(command: Union[Checkout, Commit]) -> None:
    print(command)


@dataclasses.dataclass(frozen=True)
class Checkout:
    """Checkout a branch."""

    branch: str


@dataclasses.dataclass(frozen=True)
class Commit:
    """Commit changes."""

    message: str
    all: bool = False


if __name__ == "__main__":
    dcargs.cli(main)
