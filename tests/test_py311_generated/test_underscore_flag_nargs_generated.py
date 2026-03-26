"""Tests for edge cases in nargs consumption.

Covers underscore/hyphen normalization (https://github.com/brentyi/tyro/issues/449)
and counter-style short flags (-vvv) terminating variable-length argument consumption.
"""

import dataclasses
from typing import Annotated, List, Tuple

import pytest

import tyro


def test_underscore_flag_terminates_nargs() -> None:
    """Original reproducer from the issue."""

    @dataclasses.dataclass
    class Config:
        steps: List[int] = dataclasses.field(default_factory=lambda: [10, 20, 30])
        flag_with_underscore: bool = False
        flag: bool = False

    result = tyro.cli(Config, args=["--steps", "-1", "--flag_with_underscore"])
    assert result.steps == [-1]
    assert result.flag_with_underscore is True

    # Also test with hyphens (the canonical form).
    result = tyro.cli(Config, args=["--steps", "-1", "--flag-with-underscore"])
    assert result.steps == [-1]
    assert result.flag_with_underscore is True


def test_underscore_flag_terminates_nargs_plus() -> None:
    """Test underscore flags terminate nargs='+' consumption."""

    @dataclasses.dataclass
    class Config:
        values: Tuple[int, ...] = (1,)
        learning_rate: float = 0.01

    result = tyro.cli(
        Config, args=["--values", "1", "2", "3", "--learning_rate", "0.1"]
    )
    assert result.values == (1, 2, 3)
    assert result.learning_rate == 0.1


def test_underscore_no_flag_terminates_nargs() -> None:
    """Test that --no-flag_with_underscore terminates nargs consumption."""

    @dataclasses.dataclass
    class Config:
        steps: List[int] = dataclasses.field(default_factory=lambda: [10, 20, 30])
        use_feature: bool = True

    # --no-use_feature (underscore) should terminate --steps consumption.
    result = tyro.cli(Config, args=["--steps", "1", "2", "--no-use_feature"])
    assert result.steps == [1, 2]
    assert result.use_feature is False

    # Also test with hyphens.
    result = tyro.cli(Config, args=["--steps", "1", "2", "--no-use-feature"])
    assert result.steps == [1, 2]
    assert result.use_feature is False


def test_underscore_flag_with_negative_numbers() -> None:
    """Test underscore flags work correctly alongside negative numbers."""

    @dataclasses.dataclass
    class Config:
        values: Tuple[int, ...] = ()
        my_flag: int = 0

    # Negative number followed by underscore flag.
    result = tyro.cli(Config, args=["--values", "-1", "-2", "--my_flag", "42"])
    assert result.values == (-1, -2)
    assert result.my_flag == 42

    # Interleaved negative numbers and underscore flag.
    result = tyro.cli(Config, args=["--values", "-10", "--my_flag", "-5"])
    assert result.values == (-10,)
    assert result.my_flag == -5


def test_underscore_flag_equals_syntax_terminates_nargs() -> None:
    """Test that --flag_name=value with underscores terminates nargs."""

    @dataclasses.dataclass
    class Config:
        values: Tuple[int, ...] = ()
        my_param: int = 0

    result = tyro.cli(Config, args=["--values", "1", "2", "--my_param=99"])
    assert result.values == (1, 2)
    assert result.my_param == 99


def test_underscore_flag_multiple_underscores() -> None:
    """Test flags with many underscores in the name."""

    @dataclasses.dataclass
    class Config:
        items: Tuple[str, ...] = ()
        a_b_c_d: int = 0

    result = tyro.cli(Config, args=["--items", "x", "y", "--a_b_c_d", "5"])
    assert result.items == ("x", "y")
    assert result.a_b_c_d == 5


def test_underscore_flag_with_return_unknown_args() -> None:
    """Test underscore flag normalization with return_unknown_args=True."""

    @dataclasses.dataclass
    class Config:
        values: Tuple[int, ...] = ()
        my_flag: bool = False

    result, unknown = tyro.cli(
        Config,
        args=["--values", "1", "-2", "--my_flag", "--unknown_arg"],
        return_unknown_args=True,
    )
    assert result.values == (1, -2)
    assert result.my_flag is True
    assert unknown == ["--unknown_arg"]


def test_underscore_flag_nargs_star_empty() -> None:
    """Test that an underscore flag immediately after a nargs='*' flag works
    even when zero values are consumed."""

    @dataclasses.dataclass
    class Config:
        items: List[int] = dataclasses.field(default_factory=list)
        my_option: int = 5

    result = tyro.cli(Config, args=["--items", "--my_option", "10"])
    assert result.items == []
    assert result.my_option == 10


def test_underscore_multiple_flags_terminate_nargs() -> None:
    """Test multiple underscore flags interleaved with variable-length args."""

    @dataclasses.dataclass
    class Config:
        list_a: Tuple[int, ...] = ()
        list_b: Tuple[int, ...] = ()
        some_flag: bool = False

    result = tyro.cli(
        Config,
        args=[
            "--list_a",
            "1",
            "2",
            "--some_flag",
            "--list_b",
            "3",
            "4",
            "5",
        ],
    )
    assert result.list_a == (1, 2)
    assert result.some_flag is True
    assert result.list_b == (3, 4, 5)


def test_counter_flag_terminates_nargs() -> None:
    """Test that -vvv terminates variable-length argument consumption."""

    def main(
        values: Tuple[int, ...] = (),
        verbose: Annotated[
            tyro.conf.UseCounterAction[int], tyro.conf.arg(aliases=["-v"])
        ] = 0,
    ) -> Tuple[Tuple[int, ...], int]:
        return values, verbose

    if tyro._experimental_options["backend"] != "tyro":
        pytest.skip("This test is specific to the tyro backend.")

    assert tyro.cli(main, args=["--values", "1", "2", "-vvv"]) == ((1, 2), 3)
    assert tyro.cli(main, args=["--values", "1", "-vv"]) == ((1,), 2)
    assert tyro.cli(main, args=["--values", "1", "-v"]) == ((1,), 1)


def test_counter_flag_terminates_nargs_with_negative_numbers() -> None:
    """Test that -vvv terminates nargs even after negative numbers."""

    def main(
        values: Tuple[int, ...] = (),
        verbose: Annotated[
            tyro.conf.UseCounterAction[int], tyro.conf.arg(aliases=["-v"])
        ] = 0,
    ) -> Tuple[Tuple[int, ...], int]:
        return values, verbose

    if tyro._experimental_options["backend"] != "tyro":
        pytest.skip("This test is specific to the tyro backend.")

    assert tyro.cli(main, args=["--values", "-1", "-2", "-vvv"]) == ((-1, -2), 3)


def test_counter_long_flag_terminates_nargs() -> None:
    """Test that --verbose (long form of counter) terminates nargs."""

    def main(
        values: Tuple[int, ...] = (),
        verbose: Annotated[
            tyro.conf.UseCounterAction[int], tyro.conf.arg(aliases=["-v"])
        ] = 0,
    ) -> Tuple[Tuple[int, ...], int]:
        return values, verbose

    assert tyro.cli(main, args=["--values", "1", "2", "--verbose"]) == ((1, 2), 1)
