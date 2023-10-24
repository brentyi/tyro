import contextlib
import io
import pathlib
from typing import cast

import attr
import pytest
from attrs import define, field

import tyro


def test_attrs_basic() -> None:
    @attr.s
    class ManyTypesA:
        i: tyro.conf.Positional[int] = attr.ib()
        s: str = attr.ib()
        f: float = attr.ib()
        p: pathlib.Path = attr.ib()

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
