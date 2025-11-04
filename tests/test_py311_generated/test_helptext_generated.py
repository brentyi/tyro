import dataclasses
import enum
import json
import os
import pathlib
from typing import (
    Annotated,
    Any,
    Dict,
    Generic,
    List,
    Literal,
    NotRequired,
    Optional,
    Tuple,
    TypedDict,
    TypeVar,
    cast,
)

from helptext_utils import get_helptext_with_checks

import tyro


def test_helptext() -> None:
    @dataclasses.dataclass
    class Helptext:
        """This docstring should be printed as a description."""

        x: int  # Documentation 1

        # Documentation 2
        y: Annotated[int, "ignored"]

        z: int = 3
        """Documentation 3"""

    helptext = get_helptext_with_checks(Helptext)
    assert cast(str, helptext) in helptext
    assert "x INT" in helptext
    assert "y INT" in helptext
    assert "z INT" in helptext
    assert "Documentation 1 (required)" in helptext
    assert "Documentation 2 (required)" in helptext
    assert "Documentation 3 (default: 3)" in helptext


def test_helptext_sphinx_autodoc_style() -> None:
    @dataclasses.dataclass
    class Helptext:
        """This docstring should be printed as a description."""

        x: int  #: Documentation 1

        #:Documentation 2
        y: Annotated[int, "ignored"]
        z: int = 3

    helptext = get_helptext_with_checks(Helptext)
    assert cast(str, helptext) in helptext
    assert "x INT" in helptext
    assert "y INT" in helptext
    assert "z INT" in helptext
    assert "Documentation 1 (required)" in helptext
    assert ": Documentation 1" not in helptext
    assert "Documentation 2 (required)" in helptext
    assert ":Documentation 2" not in helptext

    # :Documentation 2 should not be applied to `z`.
    assert helptext.count("Documentation 2") == 1


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

    helptext = get_helptext_with_checks(Helptext2)
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

    helptext = get_helptext_with_checks(Helptext3)
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

    helptext = get_helptext_with_checks(ChildClass)
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
        """Main function."""
        return x

    helptext = get_helptext_with_checks(main)
    assert "Main function." in helptext
    assert "Documentation 1" in helptext
    assert "Documentation 2" in helptext
    assert "__not__" not in helptext
    assert helptext.count("should be printed") == 1


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

    helptext = get_helptext_with_checks(main_with_docstring)
    assert "Documented in function" in helptext and str(Inner.__doc__) not in helptext
    assert "main_with_docstring." in helptext
    assert "Args:" not in helptext
    assert "Args:" not in helptext
    assert "Hello world!" in helptext

    helptext = get_helptext_with_checks(main_no_docstring)
    assert "Something" in helptext
    assert "main_no_docstring." in helptext
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

    helptext = get_helptext_with_checks(HelptextWithVariousDefaults)
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

    helptext = get_helptext_with_checks(HelptextMultiline)
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

    helptext = get_helptext_with_checks(HelptextGrouped)
    assert "Documentation 1 (required)" in helptext
    assert "Description of both y and z. (required)" in helptext
    assert "Description of both y and z. (default: 3)" in helptext


def test_none_default_value_helptext() -> None:
    @dataclasses.dataclass
    class Config:
        x: Optional[int] = None
        """An optional variable."""

    helptext = get_helptext_with_checks(Config)
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

    # The percent symbol needs some extra handling in argparse.
    # https://stackoverflow.com/questions/21168120/python-argparse-errors-with-in-help-string

    helptext = get_helptext_with_checks(HelptextHardString)
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

    helptext = get_helptext_with_checks(Child)
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

    helptext = get_helptext_with_checks(Child2)
    assert "--x STR" in helptext
    assert "Helptext! (default: 'This" in helptext


def test_tuple_helptext() -> None:
    @dataclasses.dataclass
    class TupleHelptext:
        x: Tuple[int, str, float]

    helptext = get_helptext_with_checks(TupleHelptext)
    assert "--x INT STR FLOAT" in helptext


def test_tuple_helptext_defaults() -> None:
    @dataclasses.dataclass
    class TupleHelptextDefaults:
        x: Tuple[int, str, str] = (5, "hello world", "hello")

    helptext = get_helptext_with_checks(TupleHelptextDefaults)
    assert "--x INT STR STR" in helptext
    assert "(default: 5 'hello world' hello)" in helptext


def test_generic_helptext() -> None:
    T = TypeVar("T")

    @dataclasses.dataclass
    class GenericTupleHelptext(Generic[T]):
        x: T

    helptext = get_helptext_with_checks(GenericTupleHelptext[int])
    assert "--x INT" in helptext


def test_generic_tuple_helptext() -> None:
    T = TypeVar("T")

    @dataclasses.dataclass
    class GenericTupleHelptext(Generic[T]):
        x: Tuple[T, T, T]

    helptext = get_helptext_with_checks(GenericTupleHelptext[int])
    assert "--x INT INT INT" in helptext


def test_generic_list_helptext() -> None:
    T = TypeVar("T")

    @dataclasses.dataclass
    class GenericTupleHelptext(Generic[T]):
        x: List[T]

    helptext = get_helptext_with_checks(GenericTupleHelptext[int])
    assert "--x [INT [INT ...]]" in helptext


def test_literal_helptext() -> None:
    @dataclasses.dataclass
    class LiteralHelptext:
        x: Literal[1, 2, 3]
        """A number."""

    helptext = get_helptext_with_checks(LiteralHelptext)
    assert "--x {1,2,3}" in helptext
    assert "A number. (required)" in helptext


def test_optional_literal_helptext() -> None:
    @dataclasses.dataclass
    class OptionalLiteralHelptext:
        x: Optional[Literal[1, 2, 3]] = None
        """A number."""

    helptext = get_helptext_with_checks(OptionalLiteralHelptext)
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
        a: Subcommand1 | Subcommand2 | Subcommand3
        # Field b description.
        b: Subcommand1 | Subcommand2 | Subcommand3
        # Field c description.
        c: Subcommand1 | Subcommand2 | Subcommand3 = dataclasses.field(
            default_factory=Subcommand3
        )

        d: bool = False

    helptext = get_helptext_with_checks(MultipleSubparsers)

    assert "2% milk." in helptext
    assert "Field a description." in helptext
    # With tyro backend, all subparser groups in the frontier are shown.
    # With argparse backend, only the first subparser group is shown.

    if tyro._experimental_options["backend"] == "tyro":
        assert "Field b description." in helptext
        assert "Field c description." in helptext
    else:
        assert "Field b description." not in helptext
        assert "Field c description." not in helptext

    # Not enough args for usage shortening to kick in.
    assert "[OPTIONS]" not in helptext
    assert "[B:SUBCOMMAND2 OPTIONS]" not in helptext

    helptext = get_helptext_with_checks(
        MultipleSubparsers,
        args=["a:subcommand1", "b:subcommand1", "--help"],
    )

    assert "2% milk." in helptext
    assert "Field a description." not in helptext
    assert "Field b description." not in helptext
    assert "Field c description." in helptext
    assert "--no-d" not in helptext
    assert "(default: c:subcommand3)" in helptext

    # Not enough args for usage shortening to kick in.
    assert "[OPTIONS]" not in helptext
    assert "[B:SUBCOMMAND1 OPTIONS]" not in helptext
    assert "[B:SUBCOMMAND2 OPTIONS]" not in helptext

    # Argument should be pushed to the leaf.
    assert "--d, --no-d" in get_helptext_with_checks(
        MultipleSubparsers,
        args=["a:subcommand1", "b:subcommand1", "c:subcommand2", "--help"],
        config=(tyro.conf.CascadeSubcommandArgs,),
    )


def test_multiple_subparsers_helptext_shortened_usage() -> None:
    @dataclasses.dataclass
    class Subcommand1:
        """2% milk."""  # % symbol is prone to bugs in argparse.

        aaaaaaa: int = 0
        bbbbbbb: int = 0
        ccccccc: int = 0
        ddddddd: int = 0
        eeeeeee: int = 0

    @dataclasses.dataclass
    class Subcommand2:
        aaaaaaa: int = 0
        bbbbbbb: int = 0
        ccccccc: int = 0
        ddddddd: int = 0
        eeeeeee: int = 0

    @dataclasses.dataclass
    class Subcommand3:
        a: int = 0
        b: int = 0
        c: int = 0
        d: int = 0
        e: int = 0

    @dataclasses.dataclass
    class MultipleSubparsers:
        # Field a description.
        a: Subcommand1 | Subcommand2 | Subcommand3
        # Field b description.
        b: Subcommand1 | Subcommand2 | Subcommand3
        # Field c description.
        c: Subcommand1 | Subcommand2 | Subcommand3 = dataclasses.field(
            default_factory=Subcommand3
        )

        ddddddd: bool = False
        fffffff: bool = False
        ggggggg: bool = False
        hhhhhhh: bool = False
        iiiiiii: bool = False

    helptext = get_helptext_with_checks(MultipleSubparsers)

    assert "2% milk." in helptext
    assert "Field a description." in helptext
    # With tyro backend, all subparser groups in the frontier are shown.
    # With argparse backend, only the first subparser group is shown.

    if tyro._experimental_options["backend"] == "tyro":
        assert "Field b description." in helptext
        assert "Field c description." in helptext
    else:
        assert "Field b description." not in helptext
        assert "Field c description." not in helptext

    assert "[OPTIONS]" in helptext
    assert "[B:SUBCOMMAND2 OPTIONS]" not in helptext

    helptext = get_helptext_with_checks(
        MultipleSubparsers, args=["a:subcommand1", "b:subcommand1", "--help"]
    )

    assert "2% milk." in helptext
    assert "Field a description." not in helptext
    assert "Field b description." not in helptext
    assert "Field c description." in helptext
    assert "(default: c:subcommand3)" in helptext

    assert "[OPTIONS]" not in helptext
    assert "[B:SUBCOMMAND1 OPTIONS]" in helptext
    assert "[B:SUBCOMMAND2 OPTIONS]" not in helptext


def test_optional_helptext() -> None:
    @dataclasses.dataclass
    class OptionalHelptext:
        """This docstring should be printed as a description. 2% milk."""

        x: Optional[int]  # Documentation 1

        # Documentation 2
        y: List[Optional[int]]

        z: Optional[int] = 3
        """Documentation 3"""

    helptext = get_helptext_with_checks(OptionalHelptext)
    assert cast(str, cast(str, OptionalHelptext.__doc__)[:20]) in helptext
    assert "2% milk" in helptext
    assert "--x {None}|INT" in helptext
    assert "--y [{None}|INT [{None}|INT ...]]" in helptext
    assert "[--z {None}|INT]" in helptext


def test_metavar_0() -> None:
    def main(x: Literal[0, 1, 2, 3] | Tuple[int, int]) -> None:
        pass

    helptext = get_helptext_with_checks(main)
    assert "--x {0,1,2,3}|{INT INT}" in helptext


def test_metavar_1() -> None:
    def main(
        x: Literal[0, 1, 2, 3] | Literal["hey,there", "hello"] | List[int],
    ) -> None:
        pass

    # The comma formatting is unfortunate, but matches argparse's default behavior.
    helptext = get_helptext_with_checks(main)
    assert "--x {0,1,2,3,hey,there,hello}|{[INT [INT ...]]}" in helptext


def test_metavar_2() -> None:
    def main(
        x: Tuple[
            Literal[0, 1, 2, 3],
            int | str,
        ],
    ) -> None:
        pass

    helptext = get_helptext_with_checks(main)
    assert "--x {0,1,2,3} INT|STR" in helptext


def test_metavar_3() -> None:
    def main(
        x: Literal[0, 1, 2, 3] | Tuple[int, int] | Tuple[str],
    ) -> None:
        pass

    helptext = get_helptext_with_checks(main)
    assert "--x {0,1,2,3}|{INT INT}|STR" in helptext


def test_metavar_4() -> None:
    def main(
        x: Literal[0, 1, 2, 3] | Tuple[int, int] | Tuple[str, str, str] | Literal[True],
    ) -> None:
        pass

    helptext = get_helptext_with_checks(main)
    assert "--x {0,1,2,3}|{INT INT}|{STR STR STR}|{True}" in helptext


def test_metavar_5() -> None:
    def main(
        x: List[Tuple[int, int] | Tuple[str, str]] = [(1, 1), (2, 2)],
    ) -> None:
        pass

    helptext = get_helptext_with_checks(main)
    assert "[--x [{INT INT}|{STR STR} [{INT INT}|{STR STR} ...]]]" in helptext


def test_metavar_6() -> None:
    def main(x: Dict[Tuple[int, int] | Tuple[str, str], Tuple[int, int]]) -> dict:
        return x

    helptext = get_helptext_with_checks(main)
    assert (
        "--x [{INT INT}|{STR STR} INT INT [{INT INT}|{STR STR} INT INT ...]]"
        in helptext
    )


def test_empty_metavar() -> None:
    """Test that empty metavar doesn't add trailing space."""

    @dataclasses.dataclass
    class Args:
        verbose: Annotated[int, tyro.conf.arg(metavar="", aliases=("-v",))] = 0

    helptext = get_helptext_with_checks(Args)
    # Should have no space after comma: "-v, --verbose".
    # Not: "-v , --verbose".
    assert "-v, --verbose" in helptext
    assert "-v , --verbose" not in helptext


def test_comment_in_subclass_list() -> None:
    @dataclasses.dataclass
    class Something(
        # This text should not show up in the helptext anywhere.
        object,
    ):
        a: int

        # But this text should!
        b: int

    helptext = get_helptext_with_checks(Something)
    assert "This text should not" not in helptext
    assert "But this text should!" in helptext


def test_pathlike() -> None:
    def main(x: os.PathLike) -> None:
        pass

    helptext = get_helptext_with_checks(main)
    assert "--x PATHLIKE " in helptext


def test_nested_bool() -> None:
    @dataclasses.dataclass
    class Child:
        x: bool = False

    def main(child: Child) -> None:
        pass

    helptext = get_helptext_with_checks(main)
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
        a: SubcommandOne | SubcommandTwo | SubcommandThree
        # Field b description.
        b: SubcommandOne | SubcommandTwo | SubcommandThree
        # Field c description.
        c: SubcommandOne | SubcommandTwo | SubcommandThree = dataclasses.field(
            default_factory=SubcommandThree
        )

    helptext = get_helptext_with_checks(MultipleSubparsers)

    assert "2% milk." in helptext
    assert "Field a description." in helptext
    # With tyro backend, all subparser groups in the frontier are shown.
    # With argparse backend, only the first subparser group is shown.

    if tyro._experimental_options["backend"] == "tyro":
        assert "Field b description." in helptext
        assert "Field c description." in helptext
    else:
        assert "Field b description." not in helptext
        assert "Field c description." not in helptext

    helptext = get_helptext_with_checks(
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
        a: SubcommandOne | SubcommandTwo | SubcommandThree
        # Field b description.
        b: SubcommandOne | SubcommandTwo | SubcommandThree
        # Field c description.
        c: SubcommandOne | SubcommandTwo | SubcommandThree = dataclasses.field(
            default_factory=SubcommandThree
        )

    helptext = get_helptext_with_checks(MultipleSubparsers, use_underscores=True)

    assert "2% milk." in helptext
    assert "Field a description." in helptext
    # With tyro backend, all subparser groups in the frontier are shown.
    # With argparse backend, only the first subparser group is shown.

    if tyro._experimental_options["backend"] == "tyro":
        assert "Field b description." in helptext
        assert "Field c description." in helptext
    else:
        assert "Field b description." not in helptext
        assert "Field c description." not in helptext

    helptext = get_helptext_with_checks(
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


def test_subparsers_wrapping() -> None:
    @dataclasses.dataclass
    class A:
        """Help message."""

        x: int

    @dataclasses.dataclass
    class CheckoutCompletion:
        """Help message."""

        y: int

    help = get_helptext_with_checks(A | CheckoutCompletion)  # type: ignore
    # Both backends use full metavar when there's a single subparser group.
    # Appears 3 times: usage line + subcommand list.
    assert help.count("checkout-completion") == 2


def test_subparsers_wrapping1() -> None:
    @dataclasses.dataclass
    class A:
        """Help message."""

        x: int

    @dataclasses.dataclass
    class CheckoutCompletio:
        """Help message."""

        y: int

    help = get_helptext_with_checks(A | CheckoutCompletio)  # type: ignore
    # Both backends use full metavar when there's a single subparser group.
    assert help.count("checkout-completio") == 2


def test_subparsers_wrapping2() -> None:
    @dataclasses.dataclass
    class A:
        """Help message."""

        x: int

    @dataclasses.dataclass
    class CheckoutCompletionn:
        """Help message."""

        y: int

    help = get_helptext_with_checks(A | CheckoutCompletionn)  # type: ignore
    # Both backends use full metavar when there's a single subparser group.
    assert help.count("checkout-completionn") == 2


def test_subparsers_wrapping3() -> None:
    @dataclasses.dataclass
    class A:
        """Help message."""

        x: int

    @dataclasses.dataclass
    class CmdCheckout012:
        """Help message."""

        y: int

    help = get_helptext_with_checks(A | CmdCheckout012)  # type: ignore
    # Both backends use full metavar when there's a single subparser group.
    assert help.count("cmd-checkout012") == 2


def test_tuple_default() -> None:
    @dataclasses.dataclass
    class A:
        """Help message."""

        x: Tuple[str, str] = ("hello", "world")

    help = get_helptext_with_checks(A)
    assert "STR STR" in help
    assert "hello world" in help
    assert "('hello', 'world')" not in help


def test_argconf_constructor() -> None:
    @dataclasses.dataclass
    class A:
        """Help message."""

        x: Annotated[
            Tuple[str, str], tyro.conf.arg(constructor=lambda x: ("a", "b"))
        ] = ("hello", "world")

    help = get_helptext_with_checks(A)
    assert "STR STR" not in help
    # Unlike case above, should not be converted to 'hello world'.
    assert "('hello', 'world')" in help  # JSON special case.


def test_argconf_constructor_json_special_case() -> None:
    @dataclasses.dataclass
    class A:
        """Help message."""

        x: Annotated[
            # NOTE: this style of JSON construction is/will be deprecated.
            # Avoid.
            Tuple[str, str],
            tyro.conf.arg(constructor=json.loads, metavar="JSON"),
        ] = ("hello", "world")
        y: Annotated[
            # NOTE: this style of JSON construction is/will be deprecated.
            # Avoid.
            Tuple[int, int],
            tyro.conf.arg(constructor=json.loads, metavar="JSON"),
        ] = (3, 5)

    help = get_helptext_with_checks(A)
    assert "STR STR" not in help
    assert "JSON" in help
    assert '["hello", "world"]' in help  # JSON special case.
    assert "[3, 5]" in help, help  # JSON special case.


def test_optional_group() -> None:
    def f(
        x: Annotated[
            # NOTE: this style of JSON construction is/will be deprecated.
            # Avoid.
            Tuple[str, str],
            tyro.conf.arg(constructor=json.loads, metavar="JSON"),
        ] = ("hello", "world"),
        y: int = 3,
    ) -> int:
        del x, y
        return 5

    help = get_helptext_with_checks(f, default=3)
    assert 'default if used: ["hello", "world"]' in help
    assert "default if used: 3" in help


def test_append_fixed() -> None:
    def f(
        x: tyro.conf.UseAppendAction[Tuple[str, str]],
        y: int = 3,
    ) -> int:
        del x, y
        return 5

    help = get_helptext_with_checks(f)
    assert "repeatable" not in help, help


def test_append_good() -> None:
    def f(
        x: tyro.conf.UseAppendAction[Tuple[str, ...]],
        y: int = 3,
    ) -> int:
        del x, y
        return 5

    help = get_helptext_with_checks(f)
    assert "repeatable" in help, help


def test_append_with_default() -> None:
    def f(
        x: tyro.conf.UseAppendAction[Tuple[str, ...]] = ("hello world", "hello"),
        y: int = 3,
    ) -> int:
        del x, y
        return 5

    help = get_helptext_with_checks(f)
    assert "repeatable, appends to: 'hello world' hello" in help, help


def test_typeddict_exclude() -> None:
    class Special(TypedDict):
        x: NotRequired[int]

    help = get_helptext_with_checks(Special)
    assert "unset by default" in help, help


def test_conf_erased_argname() -> None:
    @dataclasses.dataclass(frozen=True)
    class Verbose:
        is_verbose: bool = True

    @dataclasses.dataclass(frozen=True)
    class Args:
        verbose: Annotated[Verbose, tyro.conf.arg(name="")]

    def main(args: Args) -> None:
        print(args)

    helptext = get_helptext_with_checks(main)
    assert "args options" in helptext
    assert "args.verbose options" not in helptext


def test_long_literal_options() -> None:
    """Test that long literal options don't get truncated in helptext."""

    def main(
        x: Literal[
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
            "twenty",
        ],
    ) -> None:
        print(x)

    helptext = get_helptext_with_checks(main)

    # Check that the helptext contains all options without truncation
    for option in [
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
        "twenty",
    ]:
        assert option in helptext

    # Check that there's no ellipsis character in the helptext
    assert "…" not in helptext


def test_bool_help_edge_cases() -> None:
    """Test edge cases in metavar generation for unions with tuples and literals."""

    # Use the exact same pattern as in bool_help_edge.py but as individual function definitions
    # Currently this passes, but represents edge cases that were problematic
    def main_int(x_int: Tuple[int] | Tuple[int, int] = (1,)) -> None:
        pass

    def main_literal(
        x_literal: Tuple[Literal[0, 1, 2]]
        | Tuple[Literal[0, 1, 2], Literal[0, 1, 2]] = (0,),
    ) -> None:
        pass

    def main_bool(x_bool: Tuple[bool] | Tuple[bool, bool] = (True,)) -> None:
        pass

    # Test int case - should show INT|{INT INT}
    helptext_int = get_helptext_with_checks(main_int)
    assert "--x-int INT|{INT INT}" in helptext_int

    # Test literal case - should show {0,1,2}|{{0,1,2} {0,1,2}}
    helptext_literal = get_helptext_with_checks(main_literal)
    assert "--x-literal {0,1,2}|{{0,1,2} {0,1,2}}" in helptext_literal

    # Test bool case - should show {True,False}|{{True,False} {True,False}}
    helptext_bool = get_helptext_with_checks(main_bool)
    assert "--x-bool {True,False}|{{True,False} {True,False}}" in helptext_bool


def test_set_accent_color() -> None:
    """Test that set_accent_color runs without error."""
    tyro.extras.set_accent_color("blue")


def test_help_with_required_subcommands_consolidated() -> None:
    """Test that --help shows help text for required subcommands in consolidated mode.

    This is a regression test for an issue where --help would raise a 'Missing subcommand'
    error instead of showing the help text when using CascadeSubcommandArgs with
    required subcommands (no default).
    """
    import pytest

    @dataclasses.dataclass
    class ConfigA:
        a: int = 1

    @dataclasses.dataclass
    class ConfigB:
        b: int = 2

    def main(config: ConfigA | ConfigB) -> None:
        """Test function with required union subcommand.

        Args:
            config: Configuration to use.
        """
        pass

    # This should show help text and exit, not raise a "Missing subcommand" error.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--help"], config=(tyro.conf.CascadeSubcommandArgs,))


def test_implicit_arguments_show_required() -> None:
    """Test that default subcommand options show '(required)' indicator for required args."""

    @dataclasses.dataclass
    class SubcommandWithRequiredArg:
        """Subcommand with a required argument."""

        required_arg: int  # Required: no default value.
        optional_arg: str = "default"  # Optional: has default value.

    @dataclasses.dataclass
    class SubcommandAllOptional:
        """Another subcommand with all optional args."""

        x: int = 0

    def main(
        subcommand: SubcommandWithRequiredArg | SubcommandAllOptional = (
            SubcommandWithRequiredArg(required_arg=tyro.MISSING)  # type: ignore
        ),
    ) -> None:
        """Test function with default subcommand containing required arg.

        Args:
            subcommand: Subcommand choice with default.
        """
        pass

    # Get help text with CascadeSubcommandArgs enabled.
    # The default subcommand's arguments should appear as "implicit arguments".
    helptext = get_helptext_with_checks(
        main,
        args=["--help"],
        config=(tyro.conf.CascadeSubcommandArgs,),
    )

    # Implicit arguments only appear with tyro backend.
    if tyro._experimental_options["backend"] != "tyro":
        return

    # Check that default subcommand options section exists.
    assert "default subcommand options" in helptext

    # Check that required arg has "(required)" indicator.
    assert "--subcommand.required-arg" in helptext
    required_arg_pos = helptext.find("--subcommand.required-arg")
    assert required_arg_pos != -1
    # Look for "(required)" within a reasonable distance after the arg name.
    helptext_after_required = helptext[required_arg_pos : required_arg_pos + 150]
    assert "(required)" in helptext_after_required

    # Check that optional arg does NOT have "(required)" indicator.
    assert "--subcommand.optional-arg" in helptext
    # Find the line with the optional arg and verify it doesn't have "(required)".
    lines = helptext.split("\n")
    for line in lines:
        if "--subcommand.optional-arg" in line:
            assert "(required)" not in line
            break


def test_multiple_default_subcommands_with_required() -> None:
    """Test multiple default subcommands showing required indicators.

    This mirrors the pattern from examples/03_subcommands/03_multiple_subcommands.py
    where dataset and optimizer are both default subcommands with required fields.
    """

    @dataclasses.dataclass
    class Mnist:
        """MNIST dataset configuration."""

        binary: bool  # Required: no default value, like the example.

    @dataclasses.dataclass
    class ImageNet:
        """ImageNet dataset configuration."""

        subset: int = 1000

    @dataclasses.dataclass
    class Adam:
        """Adam optimizer configuration."""

        learning_rate: float = 1e-3

    @dataclasses.dataclass
    class Sgd:
        """SGD optimizer configuration."""

        learning_rate: float = 3e-4

    def train(
        dataset: Mnist | ImageNet = Mnist(tyro.MISSING),  # type: ignore
        optimizer: Adam | Sgd = Adam(),
    ) -> None:
        """Example training script.

        Args:
            dataset: Dataset to train on.
            optimizer: Optimizer to train with.
        """
        pass

    # Get help text with CascadeSubcommandArgs enabled.
    helptext = get_helptext_with_checks(
        train,
        args=["--help"],
        config=(tyro.conf.CascadeSubcommandArgs,),
    )

    # Implicit arguments only appear with tyro backend.
    if tyro._experimental_options["backend"] != "tyro":
        return

    # Check that default subcommand options section exists.
    assert "default subcommand options" in helptext

    # Check that the required boolean field from dataset (Mnist.binary) shows "(required)".
    assert "--dataset.binary" in helptext
    binary_pos = helptext.find("--dataset.binary")
    assert binary_pos != -1
    helptext_after_binary = helptext[binary_pos : binary_pos + 150]
    assert "(required)" in helptext_after_binary

    # Check that the optional optimizer field shows up but is NOT required.
    assert "--optimizer.learning-rate" in helptext
    lines = helptext.split("\n")
    for line in lines:
        if "--optimizer.learning-rate" in line:
            assert "(required)" not in line
            break
