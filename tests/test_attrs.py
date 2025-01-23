from __future__ import annotations

import contextlib
import io
import pathlib
from typing import Generic, TypeVar, cast

import attr
import pytest
from attrs import define, field
from helptext_utils import get_helptext_with_checks

import tyro
import tyro._strings


def test_attrs_basic() -> None:
    @attr.s
    class ManyTypesA:
        i: tyro.conf.Positional[int] = attr.ib()
        s: str = attr.ib()
        f: float = attr.ib()
        p: pathlib.Path = attr.ib()
        ignored: int = attr.ib(default=3, init=False)

    # We can directly pass a dataclass to `tyro.cli()`:
    assert tyro.cli(
        ManyTypesA,
        args=[
            "5",
            "--s",
            "5",
            "--f",
            "5",
            "--p",
            "~",
        ],
    ) == ManyTypesA(i=5, s="5", f=5.0, p=pathlib.Path("~"))


def test_attrs_defaults() -> None:
    @attr.s
    class ManyTypesB:
        i: int = attr.ib()
        s: str = attr.ib()
        f: float = attr.ib(default=1.0)

    # We can directly pass a dataclass to `tyro.cli()`:
    assert tyro.cli(
        ManyTypesB,
        args=[
            "--i",
            "5",
            "--s",
            "5",
        ],
    ) == ManyTypesB(i=5, s="5", f=1.0)


def test_attrs_helptext() -> None:
    @attr.s
    class Helptext:
        """This docstring should be printed as a description."""

        x: int = attr.ib()  # Documentation 1

        # Documentation 2
        y: int = attr.ib()

        z: int = attr.ib(default=3)
        """Documentation 3"""

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            tyro.cli(Helptext, args=["--help"])
    helptext = f.getvalue()
    assert tyro._strings.strip_ansi_sequences(cast(str, Helptext.__doc__)) in helptext

    assert "Documentation 1" in helptext
    assert "Documentation 2" in helptext
    assert "Documentation 3" in helptext


def test_attrs_next_gen_and_factory() -> None:
    @define
    class Helptext:
        """This docstring should be printed as a description."""

        x: int  # Documentation 1

        # Documentation 2
        y: int

        z: int = field(factory=lambda: 3)
        """Documentation 3"""

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            tyro.cli(Helptext, args=["--help"])
    helptext = f.getvalue()
    assert tyro._strings.strip_ansi_sequences(cast(str, Helptext.__doc__)) in helptext

    assert "Documentation 1" in helptext
    assert "Documentation 2" in helptext
    assert "Documentation 3" in helptext


def test_attrs_default_instance() -> None:
    @attr.s
    class ManyTypesB:
        i: int = attr.ib()
        s: str = attr.ib()
        f: float = attr.ib(default=1.0)
        k: float = attr.ib(default=1.0)

    assert tyro.cli(
        ManyTypesB,
        args=[
            "--i",
            "5",
            "--s",
            "5",
        ],
        default=ManyTypesB(i=5, s="5", f=2.0),
    ) == ManyTypesB(i=5, s="5", f=2.0)
    assert tyro.cli(
        ManyTypesB,
        args=["--i", "5"],
        default=ManyTypesB(i=5, s="5", f=2.0),
    ) == ManyTypesB(i=5, s="5", f=2.0)


T = TypeVar("T")


def test_attrs_inheritance_with_same_typevar() -> None:
    @attr.s
    class A(Generic[T]):
        x: T = attr.ib()

    @attr.s
    class B(A[int], Generic[T]):
        y: T = attr.ib()

    assert "INT" in get_helptext_with_checks(B[int])
    assert "STR" not in get_helptext_with_checks(B[int])
    assert "STR" in get_helptext_with_checks(B[str])
    assert "INT" in get_helptext_with_checks(B[str])

    assert tyro.cli(B[str], args=["--x", "1", "--y", "2"]) == B(x=1, y="2")
    assert tyro.cli(B[int], args=["--x", "1", "--y", "2"]) == B(x=1, y=2)


def test_diamond_inheritance() -> None:
    @define(frozen=True)
    class A:
        field: int | str = 5

    @define(frozen=True)
    class B(A):
        pass

    @define(frozen=True)
    class C(A):
        field: int = 10

    @define(frozen=True)
    class D(B, C):
        pass

    # C should come earlier int the MRO than A.
    helptext = get_helptext_with_checks(D)
    assert "5" not in helptext
    assert "10" in helptext
    assert "INT|STR" not in helptext
