# mypy: ignore-errors
"""Tests adapted from https://github.com/brentyi/tyro/issues/89, which catches edge
cases when combining nested tuple types, renamed arguments, and subcommands.

Largely written by @wookayin.
"""

import dataclasses
from pathlib import Path
from typing import Annotated, cast

import tyro.conf


@dataclasses.dataclass
class Checkout[T]:
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
        Checkout[str] | Commit,
        args=["commit", "./path.txt"],
    )
    assert o == Commit(input=Path("path.txt"))


def test_case2() -> None:
    arg, action = tyro.cli(
        tuple[
            Arg,
            Annotated[
                Checkout[str] | Commit,
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
        tuple[
            Annotated[
                Arg,
                tyro.conf.arg(name=""),
            ],
            Annotated[
                Annotated[Checkout[str], tyro.conf.subcommand(name="checkout")]
                | Annotated[Commit, tyro.conf.subcommand(name="commit")],
                tyro.conf.arg(name=""),
            ],
        ],
        args=["commit", "./path.txt"],
    )
    assert o == (Arg(), Commit(Path("./path.txt")))


def test_case4() -> None:
    o = tyro.cli(
        tuple[
            Annotated[
                Annotated[Checkout[str], tyro.conf.subcommand(name="checkout")]
                | Annotated[Commit, tyro.conf.subcommand(name="commit")],
                tyro.conf.arg(name=""),
            ]
        ],
        args=["commit", "./path.txt"],
    )
    assert o == (Commit(Path("./path.txt")),)


def test_case5() -> None:
    assert tyro.cli(
        tyro.conf.OmitArgPrefixes[
            tuple[
                Annotated[
                    Checkout[str],
                    tyro.conf.subcommand(prefix_name=False),
                ]
                | Annotated[Commit, tyro.conf.subcommand(prefix_name=False)],
                Arg,
            ]
        ],
        args=["--no-verbose", "checkout-str", "--branch", "branch"],
    ) == (Checkout("branch"), Arg(False))


# New tests using PEP 695 type aliases:

type CheckoutAlias[T] = Annotated[Checkout[T], tyro.conf.subcommand(name="checkout")]
type CommitAlias = Annotated[Commit, tyro.conf.subcommand(name="commit")]
type ActionUnion = CheckoutAlias[str] | CommitAlias
type RenamedArg = Annotated[Arg, tyro.conf.arg(name="global")]


def test_case6() -> None:
    o = tyro.cli(
        tuple[
            RenamedArg,
            Annotated[ActionUnion, tyro.conf.arg(name="")],
        ],
        args=["--global.no-verbose", "commit", "./path.txt"],
    )
    assert o == (Arg(verbose=False), Commit(Path("./path.txt")))


# https://github.com/microsoft/pyright/issues/9261
type PositionalPath = tyro.conf.Positional[Path]  # type: ignore


def test_case7() -> None:
    @dataclasses.dataclass
    class NewCommit:
        """Commit something with a message."""

        input: PositionalPath
        message: str = "Default commit message"

    o = tyro.cli(
        cast(
            type,
            CheckoutAlias[str]
            | Annotated[NewCommit, tyro.conf.subcommand(name="commit")],
        ),
        args=["commit", "./path.txt", "--message", "New commit"],
    )
    assert o == NewCommit(input=Path("./path.txt"), message="New commit")


type VerboseArg = Annotated[
    bool, tyro.conf.arg(name="verbose", help="Enable verbose output")
]


def test_case8() -> None:
    @dataclasses.dataclass
    class ConfigWithVerbose:
        action: ActionUnion
        verbose: VerboseArg = False

    o = tyro.cli(
        ConfigWithVerbose,
        args=["--verbose", "action:checkout", "--action.branch", "main"],
    )
    assert o == ConfigWithVerbose(verbose=True, action=Checkout(branch="main"))
