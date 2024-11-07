"""Argument Aliases

:func:`tyro.conf.arg()` can be used to attach aliases to arguments.

Usage:

    python ./10_aliases.py --help
    python ./10_aliases.py --branch main
    python ./10_aliases.py -b main
"""

from typing import Annotated

import tyro


def checkout(
    branch: Annotated[str, tyro.conf.arg(aliases=["-b"])],
) -> None:
    """Check out a branch."""
    print(f"{branch=}")


if __name__ == "__main__":
    tyro.cli(checkout)
