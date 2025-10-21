"""Tests to improve coverage of _tyro_backend.py."""

import dataclasses
from typing import Literal, Optional

import pytest

import tyro


def test_consolidate_misplaced_subcommand() -> None:
    """Test error when subcommand appears after other arguments in consolidated mode.

    This covers lines 870-883 in _tyro_backend.py.
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
        subcommand: SubcommandA | SubcommandB

    # This should fail because the subcommand appears after --x.
    with pytest.raises(SystemExit):
        tyro.cli(
            tyro.conf.ConsolidateSubcommandArgs[Config],
            args=["--x", "5", "subcommand:subcommand-a"],
        )


def test_consolidate_optional_nargs() -> None:
    """Test nargs='?' handling in consolidated mode.

    This covers lines 268-270, 328-329 in _tyro_backend.py.
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
        subcommand: SubcommandA | SubcommandB

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


def test_consolidate_positional_values() -> None:
    """Test variadic positional arguments in consolidated mode.

    This covers lines 799-805, 808 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class SubcommandA:
        values: tuple[int, ...]

    @dataclasses.dataclass
    class SubcommandB:
        value: int = 1

    @dataclasses.dataclass
    class Config:
        subcommand: SubcommandA | SubcommandB

    result = tyro.cli(
        tyro.conf.ConsolidateSubcommandArgs[Config],
        args=[
            "subcommand:subcommand-a",
            "--subcommand.values",
            "1",
            "2",
            "3",
        ],
    )
    assert isinstance(result.subcommand, SubcommandA)
    assert result.subcommand.values == (1, 2, 3)


def test_consolidate_nargs_plus_empty() -> None:
    """Test nargs='+' with values in consolidated mode.

    This covers lines 369-401 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class SubcommandA:
        values: tuple[int, ...]

    @dataclasses.dataclass
    class SubcommandB:
        value: int = 1

    @dataclasses.dataclass
    class Config:
        subcommand: SubcommandA | SubcommandB

    result = tyro.cli(
        tyro.conf.ConsolidateSubcommandArgs[Config],
        args=[
            "subcommand:subcommand-a",
            "--subcommand.values",
            "1",
            "2",
        ],
    )
    assert isinstance(result.subcommand, SubcommandA)
    assert result.subcommand.values == (1, 2)


def test_consolidate_count_flag() -> None:
    """Test count flags in consolidated mode.

    This covers lines 100-101, 254-256 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class SubcommandA:
        verbose: tyro.conf.UseCounterAction[int] = 0

    @dataclasses.dataclass
    class SubcommandB:
        value: int = 1

    @dataclasses.dataclass
    class Config:
        subcommand: SubcommandA | SubcommandB

    result = tyro.cli(
        tyro.conf.ConsolidateSubcommandArgs[Config],
        args=[
            "subcommand:subcommand-a",
            "--subcommand.verbose",
            "--subcommand.verbose",
            "--subcommand.verbose",
        ],
    )
    assert isinstance(result.subcommand, SubcommandA)
    assert result.subcommand.verbose == 3


def test_consolidate_flag_with_equals() -> None:
    """Test --flag=value syntax in consolidated mode.

    This covers lines 290-299 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class SubcommandA:
        value: int = 1

    @dataclasses.dataclass
    class SubcommandB:
        value: int = 2

    @dataclasses.dataclass
    class Config:
        subcommand: SubcommandA | SubcommandB

    result = tyro.cli(
        tyro.conf.ConsolidateSubcommandArgs[Config],
        args=["subcommand:subcommand-a", "--subcommand.value=42"],
    )
    assert isinstance(result.subcommand, SubcommandA)
    assert result.subcommand.value == 42


def test_consolidate_unknown_positional() -> None:
    """Test handling of unknown positional arguments in consolidated mode.

    This covers lines 811-812 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class SubcommandA:
        value: int = 1

    @dataclasses.dataclass
    class SubcommandB:
        value: int = 2

    @dataclasses.dataclass
    class Config:
        subcommand: SubcommandA | SubcommandB

    # This should fail because there's an unknown positional argument.
    with pytest.raises(SystemExit):
        tyro.cli(
            tyro.conf.ConsolidateSubcommandArgs[Config],
            args=["subcommand:subcommand-a", "unknown_positional"],
        )


def test_consolidate_default_subcommand() -> None:
    """Test default subcommand handling in consolidated mode.

    This covers lines 741-759 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class SubcommandA:
        value: int = 1

    @dataclasses.dataclass
    class SubcommandB:
        value: int = 2

    @dataclasses.dataclass
    class Config:
        subcommand: SubcommandA | SubcommandB = dataclasses.field(
            default_factory=SubcommandA
        )

    result = tyro.cli(
        tyro.conf.ConsolidateSubcommandArgs[Config],
        args=[],
        default=Config(),
    )
    assert isinstance(result.subcommand, SubcommandA)
    assert result.subcommand.value == 1


def test_recursive_mode_default_subcommand() -> None:
    """Test default subcommand in recursive mode.

    This covers lines 644-687 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class SubcommandA:
        value: int = 1

    @dataclasses.dataclass
    class SubcommandB:
        value: int = 2

    @dataclasses.dataclass
    class Config:
        subcommand: SubcommandA | SubcommandB = dataclasses.field(
            default_factory=SubcommandA
        )

    result = tyro.cli(
        Config,
        args=[],
        default=Config(),
    )
    assert isinstance(result.subcommand, SubcommandA)
    assert result.subcommand.value == 1


def test_recursive_mode_unknown_args() -> None:
    """Test unknown arguments in recursive mode cause an error.

    This covers lines 638-642 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class Config:
        value: int = 1

    # Unknown args should cause an error.
    with pytest.raises(SystemExit):
        tyro.cli(
            Config,
            args=["--value", "42", "--unknown"],
        )


def test_choices_validation() -> None:
    """Test choices validation.

    This covers lines 403-413 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class Config:
        option: Literal["a", "b", "c"]

    result = tyro.cli(Config, args=["--option", "a"])
    assert result.option == "a"

    # This should fail because "d" is not a valid choice.
    with pytest.raises(SystemExit):
        tyro.cli(Config, args=["--option", "d"])


def test_integer_nargs() -> None:
    """Test nargs with integer values.

    This covers lines 358-368 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class Config:
        values: tuple[int, int, int] = (1, 2, 3)

    result = tyro.cli(Config, args=["--values", "4", "5", "6"], default=Config())
    assert result.values == (4, 5, 6)

    # This should fail because we need exactly 3 values.
    with pytest.raises(SystemExit):
        tyro.cli(Config, args=["--values", "4", "5"], default=Config())


def test_help_flag_display() -> None:
    """Test help flag triggers help display.

    This covers lines 239-241 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class Config:
        value: int = 1

    with pytest.raises(SystemExit) as exc_info:
        tyro.cli(Config, args=["--help"])

    assert exc_info.value.code == 0


def test_consolidated_help_display() -> None:
    """Test help display in consolidated mode.

    This covers lines 773-787, 936-968 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class SubcommandA:
        value: int = 1

    @dataclasses.dataclass
    class SubcommandB:
        value: int = 2

    @dataclasses.dataclass
    class Config:
        subcommand: SubcommandA | SubcommandB

    with pytest.raises(SystemExit) as exc_info:
        tyro.cli(
            tyro.conf.ConsolidateSubcommandArgs[Config],
            args=["subcommand:subcommand-a", "--help"],
        )

    assert exc_info.value.code == 0


def test_missing_required_args_error() -> None:
    """Test error when required arguments are missing.

    This covers lines 458-471 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class Config:
        required_value: int

    with pytest.raises(SystemExit):
        tyro.cli(Config, args=[])


def test_boolean_flags() -> None:
    """Test boolean flags with store_true behavior.

    This covers lines 132-135, 248-251 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class Config:
        verbose: bool = False

    result = tyro.cli(Config, args=["--verbose"], default=Config())
    assert result.verbose is True

    result = tyro.cli(Config, args=[], default=Config())
    assert result.verbose is False


def test_nargs_star() -> None:
    """Test nargs='*' handling.

    This covers lines 369-391 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class Config:
        values: list[int] = dataclasses.field(default_factory=list)

    result = tyro.cli(Config, args=["--values", "1", "2", "3"], default=Config())
    assert result.values == [1, 2, 3]

    result = tyro.cli(Config, args=[], default=Config())
    assert result.values == []


def test_register_parser_args() -> None:
    """Test registering arguments from parser specification.

    This covers lines 145-155 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class Config:
        value1: int = 1
        value2: str = "test"
        value3: bool = False

    result = tyro.cli(
        Config,
        args=["--value1", "42", "--value2", "hello", "--value3"],
        default=Config(),
    )
    assert result.value1 == 42
    assert result.value2 == "hello"
    assert result.value3 is True


def test_add_help_flags() -> None:
    """Test help flags are registered.

    This covers lines 157-161 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class Config:
        value: int = 1

    # Test both -h and --help.
    with pytest.raises(SystemExit) as exc_info:
        tyro.cli(Config, args=["-h"])
    assert exc_info.value.code == 0

    with pytest.raises(SystemExit) as exc_info:
        tyro.cli(Config, args=["--help"])
    assert exc_info.value.code == 0


def test_validate_required_args() -> None:
    """Test validation of required arguments.

    This covers lines 436-471 in _tyro_backend.py.
    """

    @dataclasses.dataclass
    class Config:
        required1: int
        required2: str
        optional: bool = False

    # Should work with all required args.
    result = tyro.cli(
        Config,
        args=["--required1", "42", "--required2", "test"],
    )
    assert result.required1 == 42
    assert result.required2 == "test"
    assert result.optional is False

    # Should fail with missing required args.
    with pytest.raises(SystemExit):
        tyro.cli(Config, args=["--required1", "42"])


def test_nested_subcommands_consolidated() -> None:
    """Test nested subcommands in consolidated mode.

    This covers line 735 and gather_activated_parsers recursion.
    """

    @dataclasses.dataclass
    class NestedA:
        value: int = 1

    @dataclasses.dataclass
    class NestedB:
        value: int = 2

    @dataclasses.dataclass
    class SubcommandA:
        x: int = 10
        nested: NestedA | NestedB = dataclasses.field(default_factory=NestedA)

    @dataclasses.dataclass
    class Config:
        subcommand: SubcommandA = dataclasses.field(default_factory=SubcommandA)

    result = tyro.cli(
        tyro.conf.ConsolidateSubcommandArgs[Config],
        args=[],
        default=Config(),
    )
    assert isinstance(result.subcommand, SubcommandA)
    assert isinstance(result.subcommand.nested, NestedA)
