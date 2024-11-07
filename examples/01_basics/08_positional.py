"""Positional Arguments

Positional-only arguments in functions are converted to positional CLI arguments.

For more general positional arguments, see :class:`tyro.conf.Positional`.

Usage:

    python ./08_positional_args.py --help
    python ./08_positional_args.py ./a ./b
    python ./08_positional_args.py ./test1 ./test2 --verbose
"""

from __future__ import annotations

import pathlib

import tyro


def main(
    source: pathlib.Path,
    dest: pathlib.Path,
    /,  # Mark the end of positional arguments.
    verbose: bool = False,
) -> None:
    """Command-line interface defined using a function signature. Note that this
    docstring is parsed to generate helptext.

    Args:
        source: Source path.
        dest: Destination path.
        verbose: Explain what is being done.
    """
    print(f"{source=}\n{dest=}\n{verbose=}")


if __name__ == "__main__":
    tyro.cli(main)
