import dataclasses
import enum
import os
import pathlib
from collections.abc import Callable
from typing import Any, Dict, Generic, List, Optional, Tuple, TypeVar, Union, cast

import torch.nn as nn
from helptext_utils import get_helptext
from typing_extensions import Annotated, Literal


def test_helptext() -> None:
    @dataclasses.dataclass
    class Helptext:
        """This docstring should be printed as a description."""

        x: int  # Documentation 1

        # Documentation 2
        y: Annotated[int, "ignored"]

        z: int = 3
        """Documentation 3"""

    helptext = get_helptext(Helptext)
    assert cast(str, helptext) in helptext
    assert "x INT" in helptext
    assert "y INT" in helptext
    assert "z INT" in helptext
    assert "Documentation 1 (required)" in helptext
    assert "Documentation 2 (required)" in helptext
    assert "Documentation 3 (default: 3)" in helptext


def test_helptext_from_class_docstring() -> None:
    @dataclasses.dataclass
    class Helptext2:
        """This docstring should be printed as a description.

        Attributes:
            x: Documentation 1
            y: Documentation 2
            z: Documentation 3
        """

        x: int
        y: Annotated[int, "ignored"]
        z: int = 3

    helptext = get_helptext(Helptext2)
    assert "This docstring should be printed as a description" in helptext
    assert "Attributes" not in helptext
    assert "x INT" in helptext
    assert "y INT" in helptext
    assert "z INT" in helptext
    assert "Documentation 1 (required)" in helptext
    assert "Documentation 2 (required)" in helptext
    assert "Documentation 3 (default: 3)" in helptext


def test_helptext_from_class_docstring_args() -> None:
    @dataclasses.dataclass
    class Helptext3:
        """This docstring should be printed as a description.

        Args:
            x: Documentation 1
            y: Documentation 2
            z: Documentation 3
        """

        x: int
        y: Annotated[int, "ignored"]
        z: int = 3

    helptext = get_helptext(Helptext3)
    assert "This docstring should be printed as a description" in helptext
    assert "Args" not in helptext
    assert "x INT" in helptext
    assert "y INT" in helptext
    assert "z INT" in helptext
    assert "Documentation 1 (required)" in helptext
    assert "Documentation 2 (required)" in helptext
    assert "Documentation 3 (default: 3)" in helptext


def test_helptext_inherited() -> None:
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

    helptext = get_helptext(ChildClass)
    assert "Documentation 1" in helptext
    assert "Documentation 2" in helptext


def test_helptext_inherited_default_override() -> None:
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

    helptext = get_helptext(main)
    assert "Documentation 1" in helptext
    assert "Documentation 2" in helptext
    assert "__not__" not in helptext
    assert "should be printed" in helptext


def test_helptext_nested() -> None:
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

    helptext = get_helptext(main_with_docstring)
    assert "Documented in function" in helptext and str(Inner.__doc__) not in helptext
    assert "Args:" not in helptext
    assert "Hello world!" in helptext

    helptext = get_helptext(main_no_docstring)
    assert "Something" in helptext
    assert "Args:" not in helptext
    assert "Hello world!" in helptext


def test_helptext_defaults() -> None:
    class Color(enum.Enum):
        RED = enum.auto()
        GREEN = enum.auto()
        BLUE = enum.auto()

    @dataclasses.dataclass
    class HelptextWithVariousDefaults:
        x: pathlib.Path = pathlib.Path("/some/path/to/a/file")
        y: Color = Color.RED
        z: str = "%"

    helptext = get_helptext(HelptextWithVariousDefaults)
    assert "show this help message and exit" in helptext
    assert "--x PATH" in helptext
    assert "(default: /some/path/to/a/file)" in helptext
    assert "--y {RED,GREEN,BLUE}" in helptext
    assert "(default: RED)" in helptext
    assert "--z STR" in helptext
    assert "(default: %)" in helptext


def test_multiline_helptext() -> None:
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

    helptext = get_helptext(HelptextMultiline)
    assert "Documentation 1 (required)" in helptext
    assert "Documentation 2" in helptext
    assert "documentation 2" in helptext
    assert "Documentation 3" in helptext
    assert "documentation 3" in helptext


def test_grouped_helptext() -> None:
    @dataclasses.dataclass
    class HelptextGrouped:
        x: int  # Documentation 1
        # Description of both y and z.
        y: int
        z: int = 3

    helptext = get_helptext(HelptextGrouped)
    assert "Documentation 1 (required)" in helptext
    assert "Description of both y and z. (required)" in helptext
    assert "Description of both y and z. (default: 3)" in helptext


def test_none_default_value_helptext() -> None:
    @dataclasses.dataclass
    class Config:
        x: Optional[int] = None
        """An optional variable."""

    helptext = get_helptext(Config)
    assert "--x {None}|INT" in helptext
    assert "An optional variable. (default: None)" in helptext


def test_helptext_hard_bool() -> None:
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

    helptext = get_helptext(HelptextHardString)
    assert "--x" in helptext
    assert "2% milk." in helptext


def test_helptext_with_inheritance() -> None:
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

    helptext = get_helptext(Child)
    assert "--x STR" in helptext
    assert "Helptext." in helptext
    assert "(default: 'This docstring" in helptext


def test_helptext_with_inheritance_overriden() -> None:
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

    helptext = get_helptext(Child2)
    assert "--x STR" in helptext
    assert "Helptext! (default: 'This" in helptext


def test_tuple_helptext() -> None:
    @dataclasses.dataclass
    class TupleHelptext:
        x: Tuple[int, str, float]

    helptext = get_helptext(TupleHelptext)
    assert "--x INT STR FLOAT" in helptext


def test_tuple_helptext_defaults() -> None:
    @dataclasses.dataclass
    class TupleHelptextDefaults:
        x: Tuple[int, str, str] = (5, "hello world", "hello")

    helptext = get_helptext(TupleHelptextDefaults)
    assert "--x INT STR STR" in helptext
    assert "(default: 5 'hello world' hello)" in helptext


def test_generic_helptext() -> None:
    T = TypeVar("T")

    @dataclasses.dataclass
    class GenericTupleHelptext(Generic[T]):
        x: T

    helptext = get_helptext(GenericTupleHelptext[int])
    assert "--x INT" in helptext


def test_generic_tuple_helptext() -> None:
    T = TypeVar("T")

    @dataclasses.dataclass
    class GenericTupleHelptext(Generic[T]):
        x: Tuple[T, T, T]

    helptext = get_helptext(GenericTupleHelptext[int])
    assert "--x INT INT INT" in helptext


def test_generic_list_helptext() -> None:
    T = TypeVar("T")

    @dataclasses.dataclass
    class GenericTupleHelptext(Generic[T]):
        x: List[T]

    helptext = get_helptext(GenericTupleHelptext[int])
    assert "--x [INT [INT ...]]" in helptext


def test_literal_helptext() -> None:
    @dataclasses.dataclass
    class LiteralHelptext:
        x: Literal[1, 2, 3]
        """A number."""

    helptext = get_helptext(LiteralHelptext)
    assert "--x {1,2,3}" in helptext
    assert "A number. (required)" in helptext


def test_optional_literal_helptext() -> None:
    @dataclasses.dataclass
    class OptionalLiteralHelptext:
        x: Optional[Literal[1, 2, 3]] = None
        """A number."""

    helptext = get_helptext(OptionalLiteralHelptext)
    assert "--x {None,1,2,3}" in helptext
    assert "A number. (default: None)" in helptext


def test_multiple_subparsers_helptext() -> None:
    @dataclasses.dataclass
    class Subcommand1:
        """2% milk."""  # % symbol is prone to bugs in argparse.

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

    helptext = get_helptext(MultipleSubparsers)

    assert "2% milk." in helptext
    assert "Field a description." in helptext
    assert "Field b description." not in helptext
    assert "Field c description." not in helptext

    helptext = get_helptext(
        MultipleSubparsers, args=["a:subcommand1", "b:subcommand1", "--help"]
    )

    assert "2% milk." in helptext
    assert "Field a description." not in helptext
    assert "Field b description." not in helptext
    assert "Field c description." in helptext
    assert "(default: c:subcommand3)" in helptext


def test_optional_helptext() -> None:
    @dataclasses.dataclass
    class OptionalHelptext:
        """This docstring should be printed as a description. 2% milk."""

        x: Optional[int]  # Documentation 1

        # Documentation 2
        y: List[Optional[int]]

        z: Optional[int] = 3
        """Documentation 3"""

    helptext = get_helptext(OptionalHelptext)
    assert cast(str, cast(str, OptionalHelptext.__doc__)[:20]) in helptext
    assert "2% milk" in helptext
    assert "--x {None}|INT" in helptext
    assert "--y [{None}|INT [{None}|INT ...]]" in helptext
    assert "[--z {None}|INT]" in helptext


def test_metavar_0() -> None:
    def main(x: Union[Literal[0, 1, 2, 3], Tuple[int, int]]) -> None:
        pass

    helptext = get_helptext(main)
    assert "--x {0,1,2,3}|{INT INT}" in helptext


def test_metavar_1() -> None:
    def main(
        x: Union[
            Literal[0, 1, 2, 3],
            Literal["hey,there", "hello"],
            List[int],
        ]
    ) -> None:
        pass

    # The comma formatting is unfortunate, but matches argparse's default behavior.
    helptext = get_helptext(main)
    assert "--x {0,1,2,3,hey,there,hello}|{[INT [INT ...]]}" in helptext


def test_metavar_2() -> None:
    def main(
        x: Tuple[
            Literal[0, 1, 2, 3],
            Union[int, str],
        ]
    ) -> None:
        pass

    helptext = get_helptext(main)
    assert "--x {0,1,2,3} INT|STR" in helptext


def test_metavar_3() -> None:
    def main(
        x: Union[
            Literal[0, 1, 2, 3],
            Union[Tuple[int, int], Tuple[str]],
        ]
    ) -> None:
        pass

    helptext = get_helptext(main)
    assert "--x {0,1,2,3}|{INT INT}|STR" in helptext


def test_metavar_4() -> None:
    def main(
        x: Union[
            Literal[0, 1, 2, 3],
            Union[Tuple[int, int], Tuple[str, str, str]],
            Literal[True],
        ]
    ) -> None:
        pass

    helptext = get_helptext(main)
    assert "--x {0,1,2,3}|{INT INT}|{STR STR STR}|{True}" in helptext


def test_metavar_5() -> None:
    def main(
        x: List[Union[Tuple[int, int], Tuple[str, str]]] = [(1, 1), (2, 2)]
    ) -> None:
        pass

    helptext = get_helptext(main)
    assert "[--x [{INT INT}|{STR STR} [{INT INT}|{STR STR} ...]]]" in helptext


def test_metavar_6() -> None:
    def main(x: Dict[Union[Tuple[int, int], Tuple[str, str]], Tuple[int, int]]) -> dict:
        return x

    helptext = get_helptext(main)
    assert (
        "--x [{INT INT}|{STR STR} INT INT [{INT INT}|{STR STR} INT INT ...]]"
        in helptext
    )


def test_comment_in_subclass_list() -> None:
    @dataclasses.dataclass
    class Something(
        # This text should not show up in the helptext anywhere.
        object,
    ):
        a: int

        # But this text should!
        b: int

    helptext = get_helptext(Something)
    assert "This text should not" not in helptext
    assert "But this text should!" in helptext


def test_unparsable() -> None:
    class Struct:
        a: int = 5
        b: str = "7"

    def main(x: Any = Struct()):
        pass

    helptext = get_helptext(main)
    assert "--x {fixed}" in helptext

    def main2(x: Callable = nn.ReLU):
        pass

    helptext = get_helptext(main2)
    assert "--x {fixed}" in helptext
    assert "(fixed to:" in helptext
    assert "torch" in helptext


def test_pathlike() -> None:
    def main(x: os.PathLike) -> None:
        pass

    helptext = get_helptext(main)
    assert "--x PATH " in helptext


def test_nested_bool() -> None:
    @dataclasses.dataclass
    class Child:
        x: bool = False

    def main(child: Child) -> None:
        pass

    helptext = get_helptext(main)
    assert "--child.x | --child.no-x" in helptext


def test_multiple_subparsers_helptext_hyphens() -> None:
    @dataclasses.dataclass
    class SubcommandOne:
        """2% milk."""  # % symbol is prone to bugs in argparse.

        arg_x: int = 0
        arg_flag: bool = False

    @dataclasses.dataclass
    class SubcommandTwo:
        arg_y: int = 1

    @dataclasses.dataclass
    class SubcommandThree:
        arg_z: int = 2

    @dataclasses.dataclass
    class MultipleSubparsers:
        # Field a description.
        a: Union[SubcommandOne, SubcommandTwo, SubcommandThree]
        # Field b description.
        b: Union[SubcommandOne, SubcommandTwo, SubcommandThree]
        # Field c description.
        c: Union[SubcommandOne, SubcommandTwo, SubcommandThree] = dataclasses.field(
            default_factory=SubcommandThree
        )

    helptext = get_helptext(MultipleSubparsers)

    assert "2% milk." in helptext
    assert "Field a description." in helptext
    assert "Field b description." not in helptext
    assert "Field c description." not in helptext

    helptext = get_helptext(
        MultipleSubparsers, args=["a:subcommand-one", "b:subcommand-one", "--help"]
    )

    assert "2% milk." in helptext
    assert "Field a description." not in helptext
    assert "Field b description." not in helptext
    assert "Field c description." in helptext
    assert "(default: c:subcommand-three)" in helptext
    assert "--b.arg-x" in helptext
    assert "--b.no-arg-flag" in helptext
    assert "--b.arg-flag" in helptext


def test_multiple_subparsers_helptext_underscores() -> None:
    @dataclasses.dataclass
    class SubcommandOne:
        """2% milk."""  # % symbol is prone to bugs in argparse.

        arg_x: int = 0
        arg_flag: bool = False

    @dataclasses.dataclass
    class SubcommandTwo:
        arg_y: int = 1

    @dataclasses.dataclass
    class SubcommandThree:
        arg_z: int = 2

    @dataclasses.dataclass
    class MultipleSubparsers:
        # Field a description.
        a: Union[SubcommandOne, SubcommandTwo, SubcommandThree]
        # Field b description.
        b: Union[SubcommandOne, SubcommandTwo, SubcommandThree]
        # Field c description.
        c: Union[SubcommandOne, SubcommandTwo, SubcommandThree] = dataclasses.field(
            default_factory=SubcommandThree
        )

    helptext = get_helptext(MultipleSubparsers, use_underscores=True)

    assert "2% milk." in helptext
    assert "Field a description." in helptext
    assert "Field b description." not in helptext
    assert "Field c description." not in helptext

    helptext = get_helptext(
        MultipleSubparsers,
        args=["a:subcommand_one", "b:subcommand_one", "--help"],
        use_underscores=True,
    )

    assert "2% milk." in helptext
    assert "Field a description." not in helptext
    assert "Field b description." not in helptext
    assert "Field c description." in helptext
    assert "(default: c:subcommand_three)" in helptext
    assert "--b.arg_x" in helptext
    assert "--b.no_arg_flag" in helptext
    assert "--b.arg_flag" in helptext
