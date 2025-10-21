"""Tests to improve coverage of _tyro_backend.py, particularly consolidated mode."""

import dataclasses
from typing import Optional, Union

import pytest

import tyro


def test_consolidate_misplaced_subcommand() -> None:
    """Test error when subcommand appears after other arguments in consolidated mode.

    This covers lines 873-879, 891-897 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class SubcommandA:
        value: int = 1

    @dataclasses.dataclass
    class SubcommandB:
        value: int = 2

    @dataclasses.dataclass
    class Config:
        x: int
        subcommand: Union[SubcommandA, SubcommandB]

    # This should fail because the subcommand appears after --x.
    with pytest.raises(SystemExit):
        tyro.cli(
            tyro.conf.ConsolidateSubcommandArgs[Config],
            args=["--x", "5", "subcommand:subcommand-a"],
        )


def test_consolidate_optional_nargs() -> None:
    """Test nargs='?' handling in consolidated mode.

    This covers line 277 in _tyro_backend.py (the elif branch for nargs='?').
    """

    @dataclasses.dataclass
    class SubcommandA:
        required_value: int
        optional_value: Optional[int] = None

    @dataclasses.dataclass
    class SubcommandB:
        value: int = 1

    @dataclasses.dataclass
    class Config:
        subcommand: Union[SubcommandA, SubcommandB]

    # Test with the optional value provided.
    result = tyro.cli(
        tyro.conf.ConsolidateSubcommandArgs[Config],
        args=[
            "subcommand:subcommand-a",
            "--subcommand.required-value",
            "10",
            "--subcommand.optional-value",
            "42",
        ],
    )
    assert isinstance(result.subcommand, SubcommandA)
    assert result.subcommand.required_value == 10
    assert result.subcommand.optional_value == 42

    # Test without the optional value.
    result = tyro.cli(
        tyro.conf.ConsolidateSubcommandArgs[Config],
        args=["subcommand:subcommand-a", "--subcommand.required-value", "10"],
    )
    assert isinstance(result.subcommand, SubcommandA)
    assert result.subcommand.required_value == 10
    assert result.subcommand.optional_value is None


def test_consolidate_positional_append() -> None:
    """Test action='append' with positional arguments in consolidated mode.

    This covers line 329 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class SubcommandA:
        # Note: tyro doesn't directly support positional action='append',
        # but we can test the code path through variadic positionals.
        values: tuple[int, ...]

    @dataclasses.dataclass
    class SubcommandB:
        value: int = 1

    @dataclasses.dataclass
    class Config:
        subcommand: Union[SubcommandA, SubcommandB]

    result = tyro.cli(
        tyro.conf.ConsolidateSubcommandArgs[Config],
        args=["subcommand:subcommand-a", "1", "2", "3"],
    )
    assert isinstance(result.subcommand, SubcommandA)
    assert result.subcommand.values == (1, 2, 3)


def test_consolidate_nargs_plus_empty_error() -> None:
    """Test error when nargs='+' gets no values in consolidated mode.

    This covers line 396 in _tyro_backend.py (the or condition for nargs='+').
    """

    @dataclasses.dataclass
    class SubcommandA:
        values: tuple[int, ...]  # This uses nargs='+' internally.

    @dataclasses.dataclass
    class SubcommandB:
        value: int = 1

    @dataclasses.dataclass
    class Config:
        subcommand: Union[SubcommandA, SubcommandB]

    # This should fail because values requires at least one argument.
    with pytest.raises(SystemExit):
        tyro.cli(
            tyro.conf.ConsolidateSubcommandArgs[Config],
            args=["subcommand:subcommand-a"],
        )


def test_consolidate_nested_subcommands() -> None:
    """Test nested subcommands in consolidated mode.

    This covers line 737 in _tyro_backend.py (nested consolidation).
    """

    @dataclasses.dataclass
    class NestedA:
        value: int = 1

    @dataclasses.dataclass
    class NestedB:
        value: int = 2

    @dataclasses.dataclass
    class SubcommandA:
        nested: Union[NestedA, NestedB]

    @dataclasses.dataclass
    class SubcommandB:
        value: int = 1

    @dataclasses.dataclass
    class Config:
        subcommand: Union[SubcommandA, SubcommandB]

    result = tyro.cli(
        tyro.conf.ConsolidateSubcommandArgs[Config],
        args=["subcommand:subcommand-a", "subcommand.nested:nested-a", "--subcommand.nested.value", "42"],
    )
    assert isinstance(result.subcommand, SubcommandA)
    assert isinstance(result.subcommand.nested, NestedA)
    assert result.subcommand.nested.value == 42


def test_consolidate_count_flag() -> None:
    """Test count flags in consolidated mode.

    This covers line 791 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class SubcommandA:
        verbose: tyro.conf.UseCounterAction[int] = 0

    @dataclasses.dataclass
    class SubcommandB:
        value: int = 1

    @dataclasses.dataclass
    class Config:
        subcommand: Union[SubcommandA, SubcommandB]

    result = tyro.cli(
        tyro.conf.ConsolidateSubcommandArgs[Config],
        args=["subcommand:subcommand-a", "--subcommand.verbose", "--subcommand.verbose", "--subcommand.verbose"],
    )
    assert isinstance(result.subcommand, SubcommandA)
    assert result.subcommand.verbose == 3


def test_consolidate_flag_with_equals() -> None:
    """Test --flag=value syntax in consolidated mode.

    This covers line 817 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class SubcommandA:
        value: int = 1

    @dataclasses.dataclass
    class SubcommandB:
        value: int = 2

    @dataclasses.dataclass
    class Config:
        subcommand: Union[SubcommandA, SubcommandB]

    result = tyro.cli(
        tyro.conf.ConsolidateSubcommandArgs[Config],
        args=["subcommand:subcommand-a", "--subcommand.value=42"],
    )
    assert isinstance(result.subcommand, SubcommandA)
    assert result.subcommand.value == 42


def test_consolidate_unknown_positional() -> None:
    """Test handling of unknown positional arguments in consolidated mode.

    This covers lines 828-832 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class SubcommandA:
        value: int = 1

    @dataclasses.dataclass
    class SubcommandB:
        value: int = 2

    @dataclasses.dataclass
    class Config:
        subcommand: Union[SubcommandA, SubcommandB]

    # This should fail because there's an unknown positional argument.
    with pytest.raises(SystemExit):
        tyro.cli(
            tyro.conf.ConsolidateSubcommandArgs[Config],
            args=["subcommand:subcommand-a", "unknown_positional"],
        )
