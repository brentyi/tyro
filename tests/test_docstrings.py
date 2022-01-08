import contextlib
import dataclasses
import io
from typing import Optional, Tuple

import pytest

import dcargs


def test_helptext():
    @dataclasses.dataclass
    class Helptext:
        x: int  # Documentation 1

        # Documentation 2
        y: int

        z: int = 3
        """Documentation 3"""

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.parse(Helptext, args=["--help"])
    helptext = f.getvalue()
    assert "--x INT     Documentation 1\n" in helptext
    assert "--y INT     Documentation 2\n" in helptext
    assert "--z INT     Documentation 3 (default: 3)\n" in helptext


def test_multiline_helptext():
    @dataclasses.dataclass
    class HelptextMultiline:
        x: int  # Documentation 1

        # Documentation 2
        # Next line of documentation 2
        y: int

        z: int = 3
        """Documentation 3
        Next line of documentation 3"""

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.parse(HelptextMultiline, args=["--help"])
    helptext = f.getvalue()
    assert "  --x INT     Documentation 1\n" in helptext
    assert (
        "  --y INT     Documentation 2\n              Next line of documentation 2\n"
        in helptext
    )
    assert (
        "  --z INT     Documentation 3\n              Next line of documentation 3 (default: 3)\n"
        in helptext
    )


def test_none_default_value_helptext():
    @dataclasses.dataclass
    class Config:
        x: Optional[int] = None
        """An optional variable."""

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.parse(Config, args=["--help"])
    helptext = f.getvalue()
    print(helptext)
    assert "  --x INT     An optional variable. (default: None)\n" in helptext


def test_helptext_hard_bool():
    @dataclasses.dataclass
    class HelptextHardString:
        # fmt: off
        x: bool = (
            False
        )
        """Helptext. 2% milk."""
        # fmt: on

    # Note that the percent symbol needs some extra handling in argparse.
    # https://stackoverflow.com/questions/21168120/python-argparse-errors-with-in-help-string

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.parse(HelptextHardString, args=["--help"])
    helptext = f.getvalue()
    assert "--x         Helptext. 2% milk.\n" in helptext


def test_helptext_with_inheritance():
    @dataclasses.dataclass
    class Parent:
        # fmt: off
        x: str = (
            "This docstring may be tougher to parse!"
        )
        """Helptext."""
        # fmt: on

    @dataclasses.dataclass
    class Child(Parent):
        pass

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.parse(Child, args=["--help"])
    helptext = f.getvalue()
    assert (
        "--x STR     Helptext. (default: This docstring may be tougher to parse!)\n"
        in helptext
    )


def test_helptext_with_inheritance_overriden():
    @dataclasses.dataclass
    class Parent2:
        # fmt: off
        x: str = (
            "This docstring may be tougher to parse!"
        )
        """Helptext."""
        # fmt: on

    @dataclasses.dataclass
    class Child2(Parent2):
        # fmt: off
        x: str = (
            "This docstring may be tougher to parse?"
        )
        """Helptext."""
        # fmt: on

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.parse(Child2, args=["--help"])
    helptext = f.getvalue()
    assert (
        "--x STR     Helptext. (default: This docstring may be tougher to parse?)\n"
        in helptext
    )


def test_tuple_helptext():
    @dataclasses.dataclass
    class TupleHelptext:
        x: Tuple[int, str, float]

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.parse(TupleHelptext, args=["--help"])
    helptext = f.getvalue()
    assert "--x INT STR FLOAT\n" in helptext
