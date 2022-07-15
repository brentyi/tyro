"""Tests for features that are not officially features, but should work.

Includes things like omegaconf.MISSING, attrs, etc, which mostly work but either likely
have corner cases or just seem sketchy.
"""
import contextlib
import io
import pathlib
from typing import Tuple, cast

import attr
import omegaconf
import pytest

import dcargs
import dcargs._strings


def test_omegaconf_missing():
    """Passing in a omegaconf.MISSING default; this will mark an argument as required."""

    def main(
        required_a: int,
        optional: int = 3,
        required_b: int = None,  # type: ignore
    ) -> Tuple[int, int, int]:
        return (required_a, optional, required_b)  # type: ignore

    assert dcargs.cli(
        main, args="--required-a 3 --optional 4 --required-b 5".split(" ")
    ) == (3, 4, 5)
    assert dcargs.cli(main, args="--required-a 3 --required-b 5".split(" ")) == (
        3,
        3,
        5,
    )

    with pytest.raises(SystemExit):
        dcargs.cli(main, args="--required-a 3 --optional 4")
    with pytest.raises(SystemExit):
        dcargs.cli(main, args="--required-a 3")

    def main2(
        required_a: int,
        optional: int = 3,
        required_b: int = omegaconf.MISSING,
    ) -> Tuple[int, int, int]:
        return (required_a, optional, required_b)

    assert dcargs.cli(
        main2, args="--required-a 3 --optional 4 --required-b 5".split(" ")
    ) == (3, 4, 5)
    assert dcargs.cli(main2, args="--required-a 3 --required-b 5".split(" ")) == (
        3,
        3,
        5,
    )

    with pytest.raises(SystemExit):
        dcargs.cli(main2, args="--required-a 3 --optional 4")
    with pytest.raises(SystemExit):
        dcargs.cli(main2, args="--required-a 3")


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
    assert dcargs._strings.strip_color_codes(cast(str, Helptext.__doc__)) in helptext

    # Note that required detection seems to be broken here.
    assert "Documentation 1" in helptext
    assert "Documentation 2" in helptext
    assert "Documentation 3" in helptext
