"""Subcommands from Functions

We provide a shorthand for generating a subcommand CLI from a dictionary. This
is a thin wrapper around :func:`tyro.cli()`'s more verbose, type-based API. If
more generality is needed, the internal working are explained in the docs for
:func:`tyro.extras.subcommand_cli_from_dict()`.


Usage:

    python ./05_subcommands_func.py --help
    python ./05_subcommands_func.py commit --help
    python ./05_subcommands_func.py commit --message hello --all
    python ./05_subcommands_func.py checkout --help
    python ./05_subcommands_func.py checkout --branch main
"""

import tyro


def checkout(branch: str) -> None:
    """Check out a branch."""
    print(f"{branch=}")


def commit(message: str, all: bool = False) -> None:
    """Make a commit."""
    print(f"{message=} {all=}")


if __name__ == "__main__":
    tyro.extras.subcommand_cli_from_dict(
        {
            "checkout": checkout,
            "commit": commit,
        }
    )
