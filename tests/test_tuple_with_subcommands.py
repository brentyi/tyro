# mypy: disable-error-code="call-overload,misc"
#
# Mypy errors from passing union types directly into tyro.cli() as Type[T]. We would
# benefit from TypeForm[T]: https://github.com/python/mypy/issues/9773
"""Tests adapted from https://github.com/brentyi/tyro/issues/89, which catches edge
cases when combining nested tuple types, renamed arguments, and subcommands.

Largely written by @wookayin.
"""

import dataclasses
from pathlib import Path
from typing import Generic, Tuple, TypeVar, Union

from typing_extensions import Annotated

import tyro.conf

T = TypeVar("T")


@dataclasses.dataclass
class Checkout(Generic[T]):
    """Check out a branch."""

    branch: T


@dataclasses.dataclass
class Commit:
    """Commit something."""

    input: tyro.conf.Positional[Path]


@dataclasses.dataclass
class Arg:
    verbose: bool = True


def test_case1() -> None:
    o = tyro.cli(
        Union[
            Checkout[str],
            Commit,
        ],
        args=["commit", "./path.txt"],
    )
    assert o == Commit(input=Path("path.txt"))


def test_case2() -> None:
    arg, action = tyro.cli(
        Tuple[
            Arg,
            Annotated[
                Union[
                    Checkout[str],
                    Commit,
                ],
                tyro.conf.arg(name=""),
            ],
        ],
        args=["commit", "./path.txt"],
    )

    assert isinstance(arg, Arg)
    assert isinstance(action, Commit)
    assert action.input == Path("./path.txt")


def test_case3() -> None:
    o = tyro.cli(
        Tuple[
            Annotated[
                Arg,
                tyro.conf.arg(name=""),
            ],
            Annotated[
                Union[
                    Annotated[Checkout[str], tyro.conf.subcommand(name="checkout")],
                    Annotated[Commit, tyro.conf.subcommand(name="commit")],
                ],
                tyro.conf.arg(name=""),
            ],
        ],
        args=["commit", "./path.txt"],
    )
    assert o == (Arg(), Commit(Path("./path.txt")))


def test_case4() -> None:
    o = tyro.cli(
        Tuple[
            Annotated[
                Union[
                    Annotated[Checkout[str], tyro.conf.subcommand(name="checkout")],
                    Annotated[Commit, tyro.conf.subcommand(name="commit")],
                ],
                tyro.conf.arg(name=""),
            ]
        ],
        args=["commit", "./path.txt"],
    )
    assert o == (Commit(Path("./path.txt")),)


def test_case5() -> None:
    assert tyro.cli(
        tyro.conf.OmitArgPrefixes[
            Tuple[
                Union[
                    Annotated[
                        Checkout[str],
                        tyro.conf.subcommand(prefix_name=False),
                    ],
                    Annotated[Commit, tyro.conf.subcommand(prefix_name=False)],
                ],
                Arg,
            ]
        ],
        args=["--no-verbose", "checkout-str", "--branch", "branch"],
    ) == (Checkout("branch"), Arg(False))
