"""Bugs that were found while optimizing runtime."""

import contextlib
import dataclasses
import enum
import io
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import pytest
from helptext_utils import get_helptext_with_checks
from typing_extensions import Annotated, Literal, TypedDict

import tyro
import tyro._strings


def _get_error(f: Any, args: List[str]) -> str:
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stderr(target):
        tyro.cli(f, args=args)
    # Normalize whitespace, since errors can be wrapped.
    error = tyro._strings.strip_ansi_sequences(target.getvalue())
    return " ".join(error.replace("│", " ").split())


def test_unhashable_arg_default() -> None:
    """Annotated[] types can't be hashed if their metadata can't be."""

    @dataclasses.dataclass
    class Config:
        x: Annotated[List[int], tyro.conf.arg(default=[1, 2])]

    assert tyro.cli(Config, args=[]) == Config([1, 2])
    assert tyro.cli(Config, args=["--x", "3"]) == Config([3])


def test_unhashable_arg_default_generic() -> None:
    def main(x: Tuple[Annotated[List[int], tyro.conf.arg(default=[1, 2])], int]) -> Any:
        return x

    assert tyro.cli(main, args="--x.0 1 2 --x.1 3".split()) == ([1, 2], 3)


def test_union_order_is_not_shared() -> None:
    """`Union[int, str] == Union[str, int]`, but these should be parsed differently."""

    @dataclasses.dataclass
    class Config:
        a: Union[int, str] = "x"
        b: Union[str, int] = "x"
        # These will raise a warning; the default doesn't match the annotation.
        c: Union[int, str] = b"x"  # type: ignore
        d: Union[str, int] = b"x"  # type: ignore

    with pytest.warns(UserWarning):
        out = tyro.cli(Config, args="--a 5 --b 5 --c 5 --d 5".split())
    assert out == Config(a=5, b="5", c=5, d="5")


def test_literal_order_is_not_shared() -> None:
    """Literal[1, 2] == Literal[2, 1], but helptext should be different."""

    @dataclasses.dataclass
    class Config:
        a: Literal[1, 2] = 1
        b: Literal[2, 1] = 1

    helptext = get_helptext_with_checks(Config)
    assert "--a {1,2}" in helptext
    assert "--b {2,1}" in helptext


def test_union_error_labels_with_suppressed_option() -> None:
    def main(
        x: Union[Annotated[int, tyro.conf.Suppress], bool, float] = 1.0,
    ) -> None: ...

    error = _get_error(main, ["--x", "abc"])
    assert "<class 'bool'>: ['abc'] does not match choices" in error
    assert "<class 'float'>: could not convert string to float" in error
    assert "Suppress" not in error


def test_union_error_without_markup() -> None:
    def main(x: Union[int, Tuple[int, int]] = 1) -> None: ...

    error = _get_error(main, ["--x", "1", "2", "3"])
    assert "expected argument count" in error
    assert "[bold]" not in error


def test_union_empty_value_error() -> None:
    """ValueErrors don't always have a message."""

    def raises_value_error(args: List[str]) -> Any:
        raise ValueError()

    spec: Any = tyro.constructors.PrimitiveConstructorSpec(
        nargs=1,
        metavar="X",
        instance_from_str=raises_value_error,
        is_instance=lambda x: isinstance(x, bytes),
        str_from_instance=lambda x: [str(x)],
    )

    def main(x: Union[int, Annotated[bytes, spec]] = 1) -> None: ...

    assert "no type matching INT|X could be instantiated" in _get_error(
        main, ["--x", "a"]
    )


def test_union_choices_order() -> None:
    """The order of choices shouldn't depend on the hash seed."""

    spec = tyro.constructors.ConstructorRegistry.get_primitive_spec(
        tyro.constructors.PrimitiveTypeInfo.make(
            Union[Literal["e", "d", "c"], Literal["b", "a"]],  # type: ignore
            set(),
        )
    )
    assert isinstance(spec, tyro.constructors.PrimitiveConstructorSpec)
    assert spec.choices == ("e", "d", "c", "b", "a")


class Color(enum.Enum):
    RED = 1
    GREEN = 2


def test_literal_enum_choices_from_values() -> None:
    """EnumChoicesFromValues raised an error if values weren't strings."""

    def main(
        x: tyro.conf.EnumChoicesFromValues[Literal[Color.RED, Color.GREEN]] = Color.RED,
    ) -> Color:
        return x

    assert tyro.cli(main, args=[]) is Color.RED
    assert tyro.cli(main, args=["--x", "2"]) is Color.GREEN
    helptext = get_helptext_with_checks(main)
    assert "{1,2}" in helptext
    assert "(default: 1)" in helptext


def test_literal_enum_default_helptext() -> None:
    def main(x: Literal[Color.RED, Color.GREEN] = Color.RED) -> Color:
        return x

    helptext = get_helptext_with_checks(main)
    assert "{RED,GREEN}" in helptext
    assert "(default: RED)" in helptext


def test_tuple_default_for_sequence_in_union() -> None:
    def main(x: Optional[Sequence[int]] = (1, 2)) -> Any:
        return x

    assert tyro.cli(main, args=[]) == (1, 2)
    assert "(default: 1 2)" in get_helptext_with_checks(main)


def test_python_syntax_union_metavar() -> None:
    def main(
        x: tyro.conf.UsePythonSyntaxForLiteralCollections[List[Union[int, str]]] = [1],
    ) -> Any:
        return x

    helptext = get_helptext_with_checks(main)
    assert "[INT|STR,...]" in helptext
    assert tyro.cli(main, args=["--x", "[1, 'a']"]) == [1, "a"]


def test_bytes_default_helptext() -> None:
    """The default in the helptext should be a string that can be passed in."""

    def main(x: bytes = b"hi", y: bytes = b"\xff") -> Any:
        return x

    helptext = get_helptext_with_checks(main)
    assert "(default: hi)" in helptext
    assert "xff" in helptext


def test_subcommand_alias_after_variable_length_argument(backend: str) -> None:
    if backend == "argparse":
        pytest.skip("argparse doesn't support subcommands after variable-length args")

    @dataclasses.dataclass
    class A:
        x: int = 1

    @dataclasses.dataclass
    class B:
        x: int = 2

    def main(
        sub: Union[
            Annotated[A, tyro.conf.subcommand("a", aliases=("first",))],
            Annotated[B, tyro.conf.subcommand("b")],
        ],
        y: List[int] = [],
    ) -> Any:
        return sub, y

    for name in ("sub:a", "first"):
        assert tyro.cli(main, args=["--y", "1", "2", name]) == (A(1), [1, 2])


def test_delimiter_is_restored_after_exit() -> None:
    def main(a_b: int) -> None: ...

    assert tyro._strings.get_delimiter() == "-"
    _ = pytest.raises(SystemExit, tyro.cli, main, args=[], use_underscores=True)
    assert tyro._strings.get_delimiter() == "-"


def test_typeddict_excluded_dict() -> None:
    class Args(TypedDict, total=False):
        a: Dict[str, int]
        b: dict

    assert tyro.cli(Args, args=[]) == {}
    assert tyro.cli(Args, args="--a x 1".split()) == {"a": {"x": 1}}
    assert "(unset by default)" in get_helptext_with_checks(Args)


def test_empty_rows() -> None:
    from tyro import _fmtlib as fmt

    assert fmt.rows().max_width() == 0


def test_comment_above_lambda_is_not_a_field() -> None:
    @dataclasses.dataclass
    class Config:
        # Comment for x.
        x: int = 1
        y: int = 2  # Comment for y.

        x_fn = lambda x: 3  # noqa: E731

    helptext = get_helptext_with_checks(Config)
    assert "Comment for x." in helptext
    assert "Comment for y." in helptext
