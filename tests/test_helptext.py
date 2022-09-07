import contextlib
import dataclasses
import enum
import io
import pathlib
from collections.abc import Callable
from typing import Any, Dict, Generic, List, Optional, Tuple, TypeVar, Union, cast

import pytest
import torch.nn as nn
from typing_extensions import Annotated, Literal

import dcargs
import dcargs._argparse_formatter
import dcargs._strings


def _get_helptext(f: Callable, args: List[str] = ["--help"]) -> str:
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        dcargs.cli(f, args=args)

    # Check helptext with vs without termcolor. This can help catch text wrapping bugs
    # caused by ANSI sequences.
    target2 = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target2):
        with dcargs._argparse_formatter.dummy_termcolor_context():
            dcargs.cli(f, args=args)

    assert target2.getvalue() == dcargs._strings.strip_ansi_sequences(target.getvalue())
    return target2.getvalue()


def test_helptext():
    @dataclasses.dataclass
    class Helptext:
        """This docstring should be printed as a description."""

        x: int  # Documentation 1

        # Documentation 2
        y: Annotated[int, "ignored"]

        z: int = 3
        """Documentation 3"""

    helptext = _get_helptext(Helptext)
    assert cast(str, Helptext.__doc__) in helptext
    assert "x INT" in helptext
    assert "y INT" in helptext
    assert "z INT" in helptext
    assert "Documentation 1 (required)\n" in helptext
    assert "Documentation 2 (required)\n" in helptext
    assert "Documentation 3 (default: 3)\n" in helptext


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

    helptext = _get_helptext(ChildClass)
    assert "Documentation 1" in helptext
    assert "Documentation 2" in helptext


def test_helptext_inherited_default_override():
    @dataclasses.dataclass
    class ParentClass:
        """This docstring should __not__ be printed as a description."""

        x: int  # Documentation 1

        # Documentation 2
        y: int

        # fmt: off

        z: int = 3
        def some_method(self) -> None:  # noqa
            """Coverage stress test."""
        # fmt: on

    @dataclasses.dataclass
    class ChildClass(ParentClass):
        """This docstring should be printed as a description."""

    def main(x: ParentClass = ChildClass(x=5, y=5)) -> Any:
        return x

    helptext = _get_helptext(main)
    assert "Documentation 1" in helptext
    assert "Documentation 2" in helptext
    assert "__not__" not in helptext
    assert "should be printed" in helptext


def test_helptext_nested():
    """For nested classes, we should pull helptext from the outermost docstring if
    possible. The class docstring can be used as a fallback."""

    class Inner:
        def __init__(self, a: int):
            """Something

            Args:
                a (int): Hello world!
            """

    def main_with_docstring(a: Inner) -> None:
        """main_with_docstring.

        Args:
            a: Documented in function.
        """

    def main_no_docstring(a: Inner) -> None:
        """main_no_docstring."""

    helptext = _get_helptext(main_with_docstring)
    assert "Documented in function" in helptext and str(Inner.__doc__) not in helptext
    assert "Args:" not in helptext
    assert "Hello world!" in helptext

    helptext = _get_helptext(main_no_docstring)
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

    helptext = _get_helptext(HelptextWithVariousDefaults)
    assert "show this help message and exit\n  --x PATH" in helptext
    assert "(default: /some/path/to/a/file)\n" in helptext
    assert "--y {RED,GREEN,BLUE}" in helptext
    assert "(default: RED)" in helptext


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

    helptext = _get_helptext(HelptextMultiline)
    assert "Documentation 1 (required)\n" in helptext
    assert "Documentation 2" in helptext
    assert "documentation 2" in helptext
    assert "Documentation 3" in helptext
    assert "documentation 3" in helptext


def test_grouped_helptext():
    @dataclasses.dataclass
    class HelptextGrouped:
        x: int  # Documentation 1
        # Description of both y and z.
        y: int
        z: int = 3

    helptext = _get_helptext(HelptextGrouped)
    assert "Documentation 1 (required)\n" in helptext
    assert "Description of both y and z. (required)\n" in helptext
    assert "Description of both y and z. (default: 3)\n" in helptext


def test_none_default_value_helptext():
    @dataclasses.dataclass
    class Config:
        x: Optional[int] = None
        """An optional variable."""

    helptext = _get_helptext(Config)
    assert "  --x {None}|INT" in helptext
    assert "An optional variable. (default: None)\n" in helptext


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

    helptext = _get_helptext(HelptextHardString)
    assert "--x" in helptext
    assert "Helptext. 2% milk." in helptext


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

    helptext = _get_helptext(Child)
    assert "--x STR" in helptext
    assert "Helptext." in helptext
    assert "(default: 'This docstring" in helptext


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

    helptext = _get_helptext(Child2)
    assert "--x STR" in helptext
    assert "Helptext! (default: 'This" in helptext


def test_tuple_helptext():
    @dataclasses.dataclass
    class TupleHelptext:
        x: Tuple[int, str, float]

    helptext = _get_helptext(TupleHelptext)
    assert "--x INT STR FLOAT\n" in helptext


def test_tuple_helptext_defaults():
    @dataclasses.dataclass
    class TupleHelptextDefaults:
        x: Tuple[int, str, str] = (5, "hello world", "hello")

    helptext = _get_helptext(TupleHelptextDefaults)
    assert "--x INT STR STR" in helptext
    assert "(default: 5 'hello world' hello)\n" in helptext


def test_generic_helptext():
    T = TypeVar("T")

    @dataclasses.dataclass
    class GenericTupleHelptext(Generic[T]):
        x: T

    helptext = _get_helptext(GenericTupleHelptext[int])
    assert "--x INT\n" in helptext


def test_generic_tuple_helptext():
    T = TypeVar("T")

    @dataclasses.dataclass
    class GenericTupleHelptext(Generic[T]):
        x: Tuple[T, T, T]

    helptext = _get_helptext(GenericTupleHelptext[int])
    assert "--x INT INT INT\n" in helptext


def test_generic_list_helptext():
    T = TypeVar("T")

    @dataclasses.dataclass
    class GenericTupleHelptext(Generic[T]):
        x: List[T]

    helptext = _get_helptext(GenericTupleHelptext[int])
    assert "--x INT [INT ...]\n" in helptext


def test_literal_helptext():
    @dataclasses.dataclass
    class LiteralHelptext:
        x: Literal[1, 2, 3]
        """A number."""

    helptext = _get_helptext(LiteralHelptext)
    assert "--x {1,2,3}" in helptext
    assert "A number. (required)\n" in helptext


def test_optional_literal_helptext():
    @dataclasses.dataclass
    class OptionalLiteralHelptext:
        x: Optional[Literal[1, 2, 3]] = None
        """A number."""

    helptext = _get_helptext(OptionalLiteralHelptext)
    assert "--x {None,1,2,3}" in helptext
    assert "A number. (default: None)\n" in helptext


def test_multiple_subparsers_helptext():
    @dataclasses.dataclass
    class Subcommand1:
        x: int = 0

    @dataclasses.dataclass
    class Subcommand2:
        y: int = 1

    @dataclasses.dataclass
    class Subcommand3:
        z: int = 2

    @dataclasses.dataclass
    class MultipleSubparsers:
        # Field a description.
        a: Union[Subcommand1, Subcommand2, Subcommand3]
        # Field b description.
        b: Union[Subcommand1, Subcommand2, Subcommand3]
        # Field c description.
        c: Union[Subcommand1, Subcommand2, Subcommand3] = dataclasses.field(
            default_factory=Subcommand3
        )

    helptext = _get_helptext(MultipleSubparsers)

    assert "Field a description." in helptext
    assert "Field b description." not in helptext
    assert "Field c description." not in helptext

    helptext = _get_helptext(
        MultipleSubparsers, args=["a:subcommand1", "b:subcommand1", "--help"]
    )

    assert "Field a description." not in helptext
    assert "Field b description." not in helptext
    assert "Field c description." in helptext
    assert "(default: c:subcommand3)" in helptext


def test_optional_helptext():
    @dataclasses.dataclass
    class OptionalHelptext:
        """This docstring should be printed as a description."""

        x: Optional[int]  # Documentation 1

        # Documentation 2
        y: List[Optional[int]]

        z: Optional[int] = 3
        """Documentation 3"""

    helptext = _get_helptext(OptionalHelptext)
    assert cast(str, OptionalHelptext.__doc__) in helptext
    assert "--x {None}|INT" in helptext
    assert "--y {None}|INT [{None}|INT ...]\n" in helptext
    assert "[--z {None}|INT]\n" in helptext


def test_metavar_0():
    def main(x: Union[Literal[0, 1, 2, 3], Tuple[int, int]]) -> None:
        pass

    helptext = _get_helptext(main)
    assert "--x {0,1,2,3}|{INT INT}" in helptext


def test_metavar_1():
    def main(
        x: Union[
            Literal[0, 1, 2, 3],
            Literal["hey,there", "hello"],
            List[int],
        ]
    ) -> None:
        pass

    # The comma formatting is unfortunate, but matches argparse's default behavior.
    helptext = _get_helptext(main)
    assert "--x {0,1,2,3,hey,there,hello}|{INT [INT ...]}" in helptext


def test_metavar_2():
    def main(
        x: Tuple[
            Literal[0, 1, 2, 3],
            Union[int, str],
        ]
    ) -> None:
        pass

    helptext = _get_helptext(main)
    assert "--x {0,1,2,3} INT|STR" in helptext


def test_metavar_3():
    def main(
        x: Union[
            Literal[0, 1, 2, 3],
            Union[Tuple[int, int], Tuple[str]],
        ]
    ) -> None:
        pass

    helptext = _get_helptext(main)
    assert "--x {0,1,2,3}|{INT INT}|STR" in helptext


def test_metavar_4():
    def main(
        x: Union[
            Literal[0, 1, 2, 3],
            Union[Tuple[int, int], Tuple[str, str, str]],
            Literal[True],
        ]
    ) -> None:
        pass

    helptext = _get_helptext(main)
    assert "--x {0,1,2,3}|{INT INT}|{STR STR STR}|{True}" in helptext


def test_metavar_5():
    def main(
        x: List[
            Union[Tuple[int, int], Tuple[str, str]],
        ] = [(1, 1), (2, 2)]
    ) -> None:
        pass

    helptext = _get_helptext(main)
    assert "[--x {INT INT}|{STR STR} [{INT INT}|{STR STR} ...]]" in helptext


def test_metavar_6():
    def main(x: Dict[Union[Tuple[int, int], Tuple[str, str]], Tuple[int, int]]) -> dict:
        return x

    helptext = _get_helptext(main)
    assert (
        "--x {INT INT}|{STR STR} INT INT [{INT INT}|{STR STR} INT INT ...]" in helptext
    )


def test_comment_in_subclass_list():
    @dataclasses.dataclass
    class Something(
        # This text should not show up in the helptext anywhere.
        object,
    ):
        a: int

        # But this text should!
        b: int

    helptext = _get_helptext(Something)
    assert "This text should not" not in helptext
    assert "But this text should!" in helptext


def test_unparsable():
    class Struct:
        a: int = 5
        b: str = "7"

    def main(x: Any = Struct()):
        pass

    helptext = _get_helptext(main)
    assert "--x {fixed}" in helptext

    def main2(x: Callable = nn.ReLU):
        pass

    helptext = _get_helptext(main2)
    assert "--x {fixed}" in helptext
    assert "(fixed to: <class 'torch.nn" in helptext
