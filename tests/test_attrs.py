"""Tests for attrs. This is not officially supported, but most features should work.
(exceptions include default factories)"""

import contextlib
import io
import pathlib

import attr
import pytest

import dcargs


def test_attrs_basic():
    @attr.s
    class ManyTypesA:
        i: int = attr.ib()
        s: str = attr.ib()
        f: float = attr.ib()
        p: pathlib.Path = attr.ib()

    # We can directly pass a dataclass to `dcargs.cli()`:
    assert dcargs.cli(
        ManyTypesA,
        args=[
            "--i",
            "5",
            "--s",
            "5",
            "--f",
            "5",
            "--p",
            "~",
        ],
    ) == ManyTypesA(i=5, s="5", f=5.0, p=pathlib.Path("~"))


def test_attrs_defaults():
    @attr.s
    class ManyTypesB:
        i: int = attr.ib()
        s: str = attr.ib()
        f: float = attr.ib(default=1.0)

    # We can directly pass a dataclass to `dcargs.cli()`:
    assert dcargs.cli(
        ManyTypesB,
        args=[
            "--i",
            "5",
            "--s",
            "5",
        ],
    ) == ManyTypesB(i=5, s="5", f=1.0)


def test_attrs_helptext():
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
            dcargs.cli(Helptext, args=["--help"])
    helptext = f.getvalue()
    assert Helptext.__doc__ in helptext
    assert ":\n  --x INT     Documentation 1\n" in helptext
    assert "--y INT     Documentation 2\n" in helptext
    assert "--z INT     Documentation 3 (default: 3)\n" in helptext
