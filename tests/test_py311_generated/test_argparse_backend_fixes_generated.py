"""Regression tests for confirmed argparse-backend latent bugs.

Each test asserts that the argparse backend now agrees with the (correct) tyro
backend, or -- for the case argparse fundamentally cannot support -- that the
argparse backend raises a clear, explicit error instead of silently
mis-parsing.

These tests are parametrized over both backends via ``tests/conftest.py``. The
tyro backend is already correct for all three bugs; the assertions below are
written so they pass on *both* backends (the argparse backend after the fix,
the tyro backend natively).

Union members below are annotated with explicit ``subcommand()`` names so the
expected command-line tokens are deterministic regardless of class naming.
"""

from dataclasses import dataclass, field
from typing import Annotated, Optional

import pytest

import tyro
from tyro.conf import Positional, subcommand

# ----------------------------------------------------------------------------
# BUG 1: nested ``is_default`` injection skipped when a sibling subcommand
# field exists at the same level.
# ----------------------------------------------------------------------------


@dataclass
class Inner1:
    a: int = 1


@dataclass
class Inner2:
    b: int = 2


@dataclass
class MidDefault:
    pick: (
        Annotated[Inner1, subcommand("i1")]
        | Annotated[Inner2, subcommand("i2", is_default=True)]
    )


@dataclass
class MidOther:
    q: int = 0


@dataclass
class PlainArm:
    z: int = 0


@dataclass
class Top1:
    outer: (
        Annotated[MidDefault, subcommand("md", is_default=True)]
        | Annotated[MidOther, subcommand("mo")]
    )
    second: (
        Annotated[PlainArm, subcommand("plain")]
        | Annotated[MidOther, subcommand("other")]
    )


def test_bug1_nested_default_with_sibling_subcommand() -> None:
    """A default branch's nested subparser default must still be injected even
    when a later sibling subcommand field exists at the same level."""
    assert tyro.cli(Top1, args=["outer:md", "second:plain"]) == Top1(
        outer=MidDefault(pick=Inner2(b=2)), second=PlainArm(z=0)
    )


@dataclass
class P1:
    z: int = 0


@dataclass
class P2:
    w: int = 0


@dataclass
class SecondDefault:
    pk2: (
        Annotated[P1, subcommand("p1")]
        | Annotated[P2, subcommand("p2", is_default=True)]
    )


@dataclass
class Top1b:
    outer: (
        Annotated[MidDefault, subcommand("md", is_default=True)]
        | Annotated[MidOther, subcommand("mo")]
    )
    second: (
        Annotated[SecondDefault, subcommand("sd", is_default=True)]
        | Annotated[MidOther, subcommand("so")]
    )


@pytest.mark.parametrize(
    "args, expected",
    [
        ([], Top1b(MidDefault(Inner2(2)), SecondDefault(P2(0)))),
        (["outer:md"], Top1b(MidDefault(Inner2(2)), SecondDefault(P2(0)))),
        (["second:sd"], Top1b(MidDefault(Inner2(2)), SecondDefault(P2(0)))),
        (
            ["outer:md", "outer.pick:i1", "second:sd", "second.pk2:p1"],
            Top1b(MidDefault(Inner1(1)), SecondDefault(P1(0))),
        ),
    ],
)
def test_bug1_two_default_siblings(args, expected) -> None:
    assert tyro.cli(Top1b, args=args) == expected


# ----------------------------------------------------------------------------
# BUG 2: parent-level positional preceding a subcommand union.
# ----------------------------------------------------------------------------


@dataclass
class ArgA:
    x: int = 1


@dataclass
class ArgB:
    y: int = 2


@dataclass
class Top2:
    name: Positional[str]
    sub: Annotated[ArgA, subcommand("a")] | Annotated[ArgB, subcommand("b")]


def test_bug2_positional_before_subcommand() -> None:
    assert tyro.cli(Top2, args=["hello", "sub:a"]) == Top2(name="hello", sub=ArgA(x=1))
    assert tyro.cli(Top2, args=["world", "sub:b", "--sub.y", "9"]) == Top2(
        name="world", sub=ArgB(y=9)
    )


@dataclass
class Top2b:
    name: Positional[str]
    count: Positional[int]
    sub: Annotated[ArgA, subcommand("a")] | Annotated[ArgB, subcommand("b")]


def test_bug2_two_positionals_before_subcommand() -> None:
    assert tyro.cli(Top2b, args=["hello", "3", "sub:b"]) == Top2b(
        name="hello", count=3, sub=ArgB(y=2)
    )


@dataclass
class Top2c:
    name: Positional[str]
    flag: int = 0
    sub: Annotated[ArgA, subcommand("a")] | Annotated[ArgB, subcommand("b")] = field(
        default_factory=ArgA
    )


def test_bug2_positional_with_optional_and_subcommand() -> None:
    assert tyro.cli(Top2c, args=["hello", "--flag", "2", "sub:a"]) == Top2c(
        name="hello", flag=2, sub=ArgA(x=1)
    )
    assert tyro.cli(Top2c, args=["hello", "sub:a"]) == Top2c(
        name="hello", flag=0, sub=ArgA(x=1)
    )


# ----------------------------------------------------------------------------
# BUG 3: a mutex group spanning a subcommand boundary.
#
# The argparse backend cannot share a mutually-exclusive group across
# subparsers, so it raises a clear error at parser-construction time rather
# than silently mis-parsing. The tyro backend enforces the group globally and
# is correct.
# ----------------------------------------------------------------------------

_MG = tyro.conf.create_mutex_group(required=False)


@dataclass
class MutexArm:
    av: Annotated[Optional[int], _MG] = None


@dataclass
class PlainArm3:
    bv: int = 2


@dataclass
class Top3:
    top_opt: Annotated[Optional[int], _MG] = None
    sub: (
        Annotated[MutexArm, subcommand("mutex")]
        | Annotated[PlainArm3, subcommand("plain")]
    ) = field(default_factory=MutexArm)


def test_bug3_mutex_across_subcommand_boundary(backend: str) -> None:
    if backend == "argparse":
        # argparse cannot enforce a mutex group across a subparser boundary, so
        # it must reject this at construction time with a clear error (exit 2),
        # rather than silently accepting both members.
        with pytest.raises(SystemExit):
            tyro.cli(Top3, args=["--top-opt", "5", "sub:mutex", "--sub.av", "7"])
        with pytest.raises(SystemExit):
            tyro.cli(Top3, args=["--top-opt", "5", "sub:mutex"])
    else:
        # tyro backend enforces it globally: both members -> error, one -> ok.
        with pytest.raises(SystemExit):
            tyro.cli(Top3, args=["--top-opt", "5", "sub:mutex", "--sub.av", "7"])
        assert tyro.cli(Top3, args=["--top-opt", "5", "sub:mutex"]) == Top3(
            top_opt=5, sub=MutexArm(av=None)
        )


def test_bug3_mutex_across_subcommand_boundary_error_message(backend: str) -> None:
    """The argparse backend's rejection should mention the subcommand boundary."""
    if backend != "argparse":
        pytest.skip("Clear-error path is argparse-specific.")
    import io
    from contextlib import redirect_stderr

    stderr = io.StringIO()
    with redirect_stderr(stderr), pytest.raises(SystemExit):
        tyro.cli(Top3, args=["--top-opt", "5", "sub:mutex"])
    rendered = stderr.getvalue()
    assert "mutex group" in rendered
    assert "subcommand" in rendered


# A mutex group fully contained within a single (sub)command must NOT trigger
# the boundary-spanning error and must still enforce exclusion on both backends.
_MG_WITHIN = tyro.conf.create_mutex_group(required=False)


@dataclass
class ArmWithMutex:
    p: Annotated[Optional[int], _MG_WITHIN] = None
    q: Annotated[Optional[int], _MG_WITHIN] = None


@dataclass
class OtherArm:
    r: int = 0


@dataclass
class Top3Within:
    sub: (
        Annotated[ArmWithMutex, subcommand("with-mutex")]
        | Annotated[OtherArm, subcommand("other")]
    ) = field(default_factory=ArmWithMutex)


def test_bug3_mutex_within_single_subcommand_ok() -> None:
    # No member -> ok.
    assert tyro.cli(Top3Within, args=["sub:with-mutex"]) == Top3Within(
        sub=ArmWithMutex(p=None, q=None)
    )
    # One member -> ok.
    assert tyro.cli(Top3Within, args=["sub:with-mutex", "--sub.p", "1"]) == Top3Within(
        sub=ArmWithMutex(p=1, q=None)
    )
    # Both members -> mutual exclusion enforced on both backends.
    with pytest.raises(SystemExit):
        tyro.cli(
            Top3Within,
            args=["sub:with-mutex", "--sub.p", "1", "--sub.q", "2"],
        )
