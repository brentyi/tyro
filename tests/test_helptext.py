import contextlib
import dataclasses
import enum
import io
import pathlib
from typing import Generic, List, Optional, Tuple, TypeVar, cast

import pytest
from typing_extensions import Literal

import dcargs


def test_helptext():
    @dataclasses.dataclass
    class Helptext:
        """This docstring should be printed as a description."""

        x: int  # Documentation 1

        # Documentation 2
        y: int

        z: int = 3
        """Documentation 3"""

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.cli(Helptext, args=["--help"])
    helptext = f.getvalue()
    assert cast(str, Helptext.__doc__) in helptext
    assert ":\n  --x INT     Documentation 1\n" in helptext
    assert "--y INT     Documentation 2\n" in helptext
    assert "--z INT     Documentation 3 (default: 3)\n" in helptext


def test_helptext_inherited():
    class UnrelatedParentClass:
        pass

    @dataclasses.dataclass
    class ActualParentClass:
        """This docstring should be printed as a description."""

        x: int  # Documentation 1

        # Documentation 2
        y: int

        # fmt: off

        z: int = 3
        def some_method(self) -> None:  # noqa
            """Coverage stress test."""
        # fmt: on

    @dataclasses.dataclass
    class ChildClass(UnrelatedParentClass, ActualParentClass):
        pass

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.cli(ChildClass, args=["--help"])
    helptext = f.getvalue()
    assert ":\n  --x INT     Documentation 1\n" in helptext
    assert "--y INT     Documentation 2\n" in helptext


def test_helptext_nested():
    """For nested classes, we should pull helptext from the outermost docstring if
    possible. The class docstring can be used as a fallback."""

    class Inner:
        def __init__(self, a: int):
            """Something

            Args:
                a (int): Hello world!
            """
            pass

    def main_with_docstring(a: Inner) -> None:
        """main_with_docstring.

        Args:
            a: Documented in function.
        """

    def main_no_docstring(a: Inner) -> None:
        """main_no_docstring."""
        pass

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.cli(main_with_docstring, args=["--help"])
    helptext = f.getvalue()
    assert "Documented in function" in helptext and str(Inner.__doc__) not in helptext
    assert "Args:" not in helptext
    assert "Hello world!" in helptext

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.cli(main_no_docstring, args=["--help"])
    helptext = f.getvalue()
    print(helptext)
    assert "Something" in helptext
    assert "Args:" not in helptext
    assert "Hello world!" in helptext


def test_helptext_defaults():
    class Color(enum.Enum):
        RED = enum.auto()
        GREEN = enum.auto()
        BLUE = enum.auto()

    @dataclasses.dataclass
    class HelptextWithVariousDefaults:
        x: pathlib.Path = pathlib.Path("/some/path/to/a/file")
        y: Color = Color.RED

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.cli(HelptextWithVariousDefaults, args=["--help"])
    helptext = f.getvalue()
    assert (
        "show this help message and exit\n  --x PATH              (default:"
        " /some/path/to/a/file)\n" in helptext
    )
    assert "--y {RED,GREEN,BLUE}  (default: RED)\n" in helptext


def test_multiline_helptext():
    @dataclasses.dataclass
    class HelptextMultiline:
        x: int  # Documentation 1

        # This comment should be ignored!

        # Documentation 2
        # Next line of documentation 2
        y: int

        z: int = 3
        """Documentation 3
        Next line of documentation 3"""

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.cli(HelptextMultiline, args=["--help"])
    helptext = f.getvalue()
    assert "  --x INT     Documentation 1\n" in helptext
    assert (
        "  --y INT     Documentation 2\n              Next line of documentation 2\n"
        in helptext
    )
    assert (
        "  --z INT     Documentation 3\n              Next line of documentation 3"
        " (default: 3)\n" in helptext
    )


def test_grouped_helptext():
    @dataclasses.dataclass
    class HelptextGrouped:
        x: int  # Documentation 1
        # Description of both y and z.
        y: int
        z: int = 3

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.cli(HelptextGrouped, args=["--help"])
    helptext = f.getvalue()
    assert "  --x INT     Documentation 1\n" in helptext
    assert "  --y INT     Description of both y and z.\n" in helptext
    assert "  --z INT     Description of both y and z. (default: 3)\n" in helptext


def test_none_default_value_helptext():
    @dataclasses.dataclass
    class Config:
        x: Optional[int] = None
        """An optional variable."""

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.cli(Config, args=["--help"])
    helptext = f.getvalue()
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
            dcargs.cli(HelptextHardString, args=["--help"])
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
            dcargs.cli(Child, args=["--help"])
    helptext = f.getvalue()
    assert (
        "--x STR     Helptext. (default: 'This docstring may be tougher to parse!')\n"
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
        """Helptext!"""
        # fmt: on

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.cli(Child2, args=["--help"])
    helptext = f.getvalue()
    assert (
        "--x STR     Helptext! (default: 'This docstring may be tougher to parse?')\n"
        in helptext
    )


def test_tuple_helptext():
    @dataclasses.dataclass
    class TupleHelptext:
        x: Tuple[int, str, float]

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.cli(TupleHelptext, args=["--help"])
    helptext = f.getvalue()
    assert "--x INT STR FLOAT\n" in helptext


def test_tuple_helptext_defaults():
    @dataclasses.dataclass
    class TupleHelptextDefaults:
        x: Tuple[int, str, str] = (5, "hello world", "hello")

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.cli(TupleHelptextDefaults, args=["--help"])
    helptext = f.getvalue()
    assert "--x INT STR STR  (default: 5 'hello world' hello)\n" in helptext


def test_generic_helptext():
    T = TypeVar("T")

    @dataclasses.dataclass
    class GenericTupleHelptext(Generic[T]):
        x: T

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.cli(GenericTupleHelptext[int], args=["--help"])
    helptext = f.getvalue()
    assert "--x INT\n" in helptext


def test_generic_tuple_helptext():
    T = TypeVar("T")

    @dataclasses.dataclass
    class GenericTupleHelptext(Generic[T]):
        x: Tuple[T, T, T]

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.cli(GenericTupleHelptext[int], args=["--help"])
    helptext = f.getvalue()
    assert "--x INT INT INT\n" in helptext


def test_generic_list_helptext():
    T = TypeVar("T")

    @dataclasses.dataclass
    class GenericTupleHelptext(Generic[T]):
        x: List[T]

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.cli(GenericTupleHelptext[int], args=["--help"])
    helptext = f.getvalue()
    assert "--x INT [INT ...]\n" in helptext


def test_literal_helptext():
    @dataclasses.dataclass
    class LiteralHelptext:
        x: Literal[1, 2, 3]
        """A number."""

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.cli(LiteralHelptext, args=["--help"])
    helptext = f.getvalue()
    assert "--x {1,2,3}  A number.\n" in helptext


def test_optional_literal_helptext():
    @dataclasses.dataclass
    class OptionalLiteralHelptext:
        x: Optional[Literal[1, 2, 3]]
        """A number."""

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.cli(OptionalLiteralHelptext, args=["--help"])
    helptext = f.getvalue()
    assert "--x {1,2,3}  A number. (default: None)\n" in helptext
