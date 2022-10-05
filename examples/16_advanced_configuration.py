"""The :mod:`tyro.conf` module contains utilities that can be used to configure
command-line interfaces beyond what is expressible via static type annotations.

Features here are supported, but generally unnecessary and should be used sparingly.

Usage:
`python ./16_advanced_configuration.py --help`
"""

import dataclasses
from typing import Union

from typing_extensions import Annotated

import tyro


@dataclasses.dataclass(frozen=True)
class CheckoutArgs:
    """Checkout a branch."""

    branch: str


@dataclasses.dataclass(frozen=True)
class CommitArgs:
    """Commit changes."""

    message: str
    all: bool = False


@dataclasses.dataclass
class Args:
    # A boolean field with flag conversion turned off.
    boolean: tyro.conf.FlagConversionOff[bool] = False

    # A numeric field parsed as a positional argument.
    positional: tyro.conf.Positional[int] = 3

    # A numeric field that can't be changed via the CLI.
    fixed: tyro.conf.Fixed[int] = 5

    # A union over nested structures, but without subcommand generation. When a default
    # is provided, the type is simply fixed to that default.
    union_without_subcommand: tyro.conf.AvoidSubcommands[
        Union[CheckoutArgs, CommitArgs]
    ] = CheckoutArgs("main")

    # `tyro.conf.subcommand()` can be used to configure subcommands in a Union. Here,
    # we make the subcommand names more succinct.
    renamed_subcommand: Union[
        Annotated[
            CheckoutArgs, tyro.conf.subcommand(name="checkout", prefix_name=False)
        ],
        Annotated[CommitArgs, tyro.conf.subcommand(name="commit", prefix_name=False)],
    ] = CheckoutArgs("main")


if __name__ == "__main__":
    print(tyro.cli(Args))
