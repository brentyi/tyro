"""Argument aliases

:func:`tyro.conf.arg()` can be used to attach aliases to arguments.

Usage:
`python ./11_aliases.py --help`
`python ./11_aliases.py commit --help`
`python ./11_aliases.py commit --message hello --all`
`python ./11_aliases.py commit -m hello -a`
`python ./11_aliases.py checkout --help`
`python ./11_aliases.py checkout --branch main`
`python ./11_aliases.py checkout -b main`
"""

from typing_extensions import Annotated

import tyro


def checkout(
    branch: Annotated[str, tyro.conf.arg(aliases=["-b"])],
) -> None:
    """Check out a branch."""
    print(f"{branch=}")


def commit(
    message: Annotated[str, tyro.conf.arg(aliases=["-m"])],
    all: Annotated[bool, tyro.conf.arg(aliases=["-a"])] = False,
) -> None:
    """Make a commit."""
    print(f"{message=} {all=}")


if __name__ == "__main__":
    tyro.extras.subcommand_cli_from_dict(
        {
            "checkout": checkout,
            "commit": commit,
        }
    )
