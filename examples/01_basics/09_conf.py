"""Configuration via typing.Annotated[]

The :mod:`tyro.conf` module contains utilities that can be used in conjunction
with :py:data:`typing.Annotated` to configure command-line interfaces beyond
what is expressible via static type annotations. To apply options globally,
these same flags can also be passed via the ``config`` argument of
:func:`tyro.cli`.

Features here are supported, but generally unnecessary and should be used sparingly.

Usage:

    python ./09_conf.py --help
    python ./09_conf.py 5 --boolean True
"""

import dataclasses

from typing_extensions import Annotated

import tyro


@dataclasses.dataclass
class Args:
    # A numeric field parsed as a positional argument.
    positional: tyro.conf.Positional[int]

    # A boolean field.
    boolean: bool = False

    # A numeric field that can't be changed via the CLI.
    fixed: tyro.conf.Fixed[int] = 5

    # A field with manually overridden properties.
    manual: Annotated[
        str,
        tyro.conf.arg(
            name="renamed",
            metavar="STRING",
            help="A field with manually overridden properties!",
        ),
    ] = "Hello"


if __name__ == "__main__":
    print(tyro.cli(Args, config=(tyro.conf.FlagConversionOff,)))
