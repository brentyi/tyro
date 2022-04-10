from __future__ import annotations

import dataclasses
from typing import Union

import dcargs


@dataclasses.dataclass(frozen=True)
class Args:
    """Example of a version control-style subcommand interface."""

    # Subcommand to use; we support "checkout" and "commit".
    #
    # If desired, we also support default values for subparsers, eg
    #     command: Union[Checkout, Commit] = Checkout("main")
    command: Union[Checkout, Commit]


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
    # args = dcargs.parse(Args)
    args = dcargs.parse(Args, default_instance=Args(command=Checkout(branch="main")))
    print(args)
