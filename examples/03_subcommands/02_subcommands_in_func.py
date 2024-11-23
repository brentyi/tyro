"""Subcommands as Function Arguments

A subcommand will be created for each input annotated with a union over
struct types.

.. note::

    To prevent :func:`tyro.cli()` from converting a Union type into a subcommand,
    use :class:`tyro.conf.AvoidSubcommands`.

.. note::

    Argument ordering for subcommands can be tricky. In the example below,
    ``--shared-arg`` must always come *before* the subcommand. As an option for
    alleviating this, see :class:`tyro.conf.ConsolidateSubcommandArgs`.


Usage:

    # Print the helptext. This will show the available subcommands:
    python ./02_subcommands_in_func.py --help

    # Using the default subcommand:
    python ./02_subcommands_in_func.py --shared-arg 100

    # Choosing a different subcommand:
    python ./02_subcommands_in_func.py --shared-arg 100 cmd:commit --cmd.message Hello!
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


def main(
    shared_arg: int,
    cmd: Checkout | Commit = Checkout(branch="default"),
):
    print(f"{shared_arg=}")
    print(cmd)


if __name__ == "__main__":
    tyro.cli(main)
