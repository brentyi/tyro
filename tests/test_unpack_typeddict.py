"""Tests for Unpack[TypedDict] support in **kwargs."""

from typing import NotRequired, Required

import pytest
from typing_extensions import TypedDict, Unpack

import tyro


class BasicOptions(TypedDict):
    """Basic TypedDict with required and optional fields."""

    option_a: str
    option_b: NotRequired[str]
    option_c: NotRequired[int]


class TotalFalseOptions(TypedDict, total=False):
    """TypedDict with total=False (all fields optional)."""

    option_a: str
    option_b: int


class MixedTotalFalseOptions(TypedDict, total=False):
    """TypedDict with total=False but some Required fields."""

    option_a: Required[str]
    option_b: int


def test_basic_unpack_kwargs() -> None:
    """Test basic Unpack[TypedDict] with required and optional fields."""

    def main(regular_arg: int, **kwargs: Unpack[BasicOptions]) -> dict:
        return {"regular": regular_arg, "kwargs": kwargs}

    # All fields provided.
    result = tyro.cli(
        main,
        args=[
            "--regular-arg",
            "42",
            "--kwargs.option-a",
            "hello",
            "--kwargs.option-b",
            "world",
            "--kwargs.option-c",
            "123",
        ],
    )
    assert result == {
        "regular": 42,
        "kwargs": {"option_a": "hello", "option_b": "world", "option_c": 123},
    }


def test_unpack_kwargs_required_only() -> None:
    """Test that only required field is mandatory."""

    def main(**kwargs: Unpack[BasicOptions]) -> dict:
        return dict(kwargs)

    # Only required field.
    result = tyro.cli(main, args=["--kwargs.option-a", "hello"])
    assert result == {"option_a": "hello"}


def test_unpack_kwargs_missing_required() -> None:
    """Test error when required field is missing."""

    def main(**kwargs: Unpack[BasicOptions]) -> dict:
        return dict(kwargs)

    with pytest.raises(SystemExit):
        tyro.cli(main, args=[])


def test_unpack_kwargs_total_false() -> None:
    """Test total=False TypedDict where all fields are optional."""

    def main(**kwargs: Unpack[TotalFalseOptions]) -> dict:
        return dict(kwargs)

    # No fields - should work.
    result = tyro.cli(main, args=[])
    assert result == {}

    # Some fields.
    result = tyro.cli(main, args=["--kwargs.option-a", "hello"])
    assert result == {"option_a": "hello"}


def test_unpack_kwargs_mixed_total_false() -> None:
    """Test total=False with Required[] fields."""

    def main(**kwargs: Unpack[MixedTotalFalseOptions]) -> dict:
        return dict(kwargs)

    # Required field only.
    result = tyro.cli(main, args=["--kwargs.option-a", "hello"])
    assert result == {"option_a": "hello"}

    # Missing required field should error.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=[])


def test_unpack_kwargs_with_class() -> None:
    """Test Unpack[TypedDict] in class __init__."""

    class MyClass:
        def __init__(self, name: str, **kwargs: Unpack[BasicOptions]) -> None:
            self.name = name
            self.kwargs = kwargs

    result = tyro.cli(MyClass, args=["--name", "test", "--kwargs.option-a", "value"])
    assert result.name == "test"
    assert result.kwargs == {"option_a": "value"}


def test_unpack_kwargs_with_args() -> None:
    """Test Unpack[TypedDict] combined with *args."""

    class MyClass:
        def __init__(self, *args: str, **kwargs: Unpack[BasicOptions]) -> None:
            self.args = args
            self.kwargs = kwargs

    result = tyro.cli(
        MyClass,
        args=["--args", "a", "b", "--kwargs.option-a", "hello"],
    )
    assert result.args == ("a", "b")
    assert result.kwargs == {"option_a": "hello"}


def test_plain_kwargs_still_works() -> None:
    """Test that plain **kwargs without Unpack still works."""

    def main(**kwargs: float) -> dict:
        return dict(kwargs)

    result = tyro.cli(main, args=["--kwargs", "learning_rate", "0.001", "beta", "0.9"])
    assert result == {"learning_rate": 0.001, "beta": 0.9}


def test_consistency_regular_vs_variadic_args() -> None:
    """Test consistent behavior between regular args and *args with Unpack[TypedDict].

    This test verifies that both FirstType (regular `args: str` parameter) and
    SecondType (`*args: str` variadic parameter) work correctly with
    `**kwargs: Unpack[TypedDict]`.
    """

    class Options(TypedDict):
        option_a: str
        option_b: NotRequired[str]

    class FirstType:
        """Class with regular args parameter and Unpack kwargs."""

        def __init__(self, args: str, **kwargs: Unpack[Options]) -> None:
            self.args = args
            self.kwargs = kwargs

    class SecondType:
        """Class with variadic *args and Unpack kwargs."""

        def __init__(self, *args: str, **kwargs: Unpack[Options]) -> None:
            self.args = args
            self.kwargs = kwargs

    # Test FirstType.
    first = tyro.cli(
        FirstType,
        args=["--args", "hello", "--kwargs.option-a", "value_a"],
    )
    assert first.args == "hello"
    assert first.kwargs == {"option_a": "value_a"}

    # Test SecondType.
    second = tyro.cli(
        SecondType,
        args=["--args", "hello", "--kwargs.option-a", "value_a"],
    )
    assert second.args == ("hello",)
    assert second.kwargs == {"option_a": "value_a"}

    # Test with optional kwargs field.
    first = tyro.cli(
        FirstType,
        args=[
            "--args",
            "hello",
            "--kwargs.option-a",
            "value_a",
            "--kwargs.option-b",
            "value_b",
        ],
    )
    assert first.args == "hello"
    assert first.kwargs == {"option_a": "value_a", "option_b": "value_b"}

    second = tyro.cli(
        SecondType,
        args=[
            "--args",
            "x",
            "y",
            "z",
            "--kwargs.option-a",
            "value_a",
            "--kwargs.option-b",
            "value_b",
        ],
    )
    assert second.args == ("x", "y", "z")
    assert second.kwargs == {"option_a": "value_a", "option_b": "value_b"}
