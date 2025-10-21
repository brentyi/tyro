"""Mutually Exclusive Groups

:func:`tyro.conf.create_mutex_group()` can be used to create mutually exclusive
argument groups, where either exactly one (required=True) or at most one
(required=False) argument from the group can be specified.

The ``title`` parameter can be used to customize the group title in the help text.

Usage:

    python ./14_mutex.py
    python ./14_mutex.py --help
    python ./14_mutex.py --target-stream stdout
    python ./14_mutex.py --target-file /tmp/output.txt
    python ./14_mutex.py --target-stream stdout --verbose
    python ./14_mutex.py --target-file /tmp/output.txt --very-verbose
    python ./14_mutex.py --target-stream stdout --target-file /tmp/output.txt
    python ./14_mutex.py --target-stream stdout --verbose --very-verbose
"""

from pathlib import Path
from typing import Annotated, Literal

import tyro

RequiredGroup = tyro.conf.create_mutex_group(required=True, title="output target")
OptionalGroup = tyro.conf.create_mutex_group(required=False, title="verbosity level")


def main(
    # Exactly one of --target-stream or --target-file must be specified.
    target_stream: Annotated[Literal["stdout", "stderr"] | None, RequiredGroup] = None,
    target_file: Annotated[Path | None, RequiredGroup] = None,
    # Either --verbose or --very-verbose can be specified (but not both).
    verbose: Annotated[bool, OptionalGroup] = False,
    very_verbose: Annotated[bool, OptionalGroup] = False,
) -> None:
    """Demonstrate mutually exclusive argument groups."""
    if very_verbose or verbose:
        print(f"{target_stream=} {target_file=}")
    if very_verbose:
        print(f"{target_stream=} {target_file=}")


if __name__ == "__main__":
    tyro.cli(
        main,
        # `DisallowNone` prevents `None` from being a valid choice for
        # `--target-stream` and `--target-file`.
        #
        # `FlagCreatePairsOff` prevents `--no-verbose` and `--no-very-verbose` from
        # being created.
        config=(tyro.conf.DisallowNone, tyro.conf.FlagCreatePairsOff),
    )
