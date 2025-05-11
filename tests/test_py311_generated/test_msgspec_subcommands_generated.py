import dataclasses
import enum
from pathlib import Path
from typing import Any, Callable, Generic, Optional, TypeVar, cast

import msgspec
import pytest
from helptext_utils import get_helptext_with_checks

import tyro

# Define TypeVars for generics tests
T = TypeVar("T")
S = TypeVar("S")


def as_callable(union_type: Any) -> Callable[..., Any]:
    """Helper function to cast Union types as callables for type checking.

    This is needed because pyright expects get_helptext_with_checks to receive a callable,
    but we're passing Union types directly. The actual runtime behavior is unchanged.
    """
    return cast(Callable[..., Any], union_type)


def test_basic_msgspec_subcommands():
    """Test basic msgspec subcommands with Union types."""

    class Checkout(msgspec.Struct):
        """Checkout a branch."""

        branch: str

    class Commit(msgspec.Struct):
        """Commit changes."""

        message: str
        amend: bool = False

    # Test checkout subcommand
    result = tyro.cli(
        as_callable(Checkout | Commit), args=["checkout", "--branch", "main"]
    )
    assert isinstance(result, Checkout)
    assert result.branch == "main"

    # Test commit subcommand
    result = tyro.cli(
        as_callable(Checkout | Commit),
        args=["commit", "--message", "Initial commit"],
    )
    assert isinstance(result, Commit)
    assert result.message == "Initial commit"
    assert result.amend is False

    # Test commit with additional flag
    result = tyro.cli(
        as_callable(Checkout | Commit),
        args=["commit", "--message", "Fix bug", "--amend"],
    )
    assert isinstance(result, Commit)
    assert result.message == "Fix bug"
    assert result.amend is True

    # Verify helptext
    helptext = get_helptext_with_checks(as_callable(Checkout | Commit))
    assert "checkout" in helptext
    assert "commit" in helptext
    assert "Checkout a branch" in helptext
    assert "Commit changes" in helptext


def test_msgspec_subcommands_with_same_type_different_generics():
    """Test msgspec subcommands with the same type but different generic parameters."""

    class Process(msgspec.Struct, Generic[T]):
        """Process data of a specific type."""

        data: T
        debug: bool = False

    # Create command with different generic instantiations
    Command = Process[int] | Process[str]

    # This will work with tyro if the CLI args can disambiguate the types
    # Test with int type (first option in union)
    result_int = tyro.cli(as_callable(Command), args=["process-int", "--data", "42"])
    assert isinstance(result_int, Process)
    assert result_int.data == 42

    # Test with str type (second option in union)
    result_str = tyro.cli(as_callable(Command), args=["process-str", "--data", "hello"])
    assert isinstance(result_str, Process)
    assert result_str.data == "hello"


def test_msgspec_mixed_dataclass_and_msgspec_subcommands():
    """Test mixing dataclass and msgspec types in subcommands."""

    @dataclasses.dataclass
    class DataclassCommand:
        """A command implemented as a dataclass."""

        value: int
        flag: bool = False

    class MsgspecCommand(msgspec.Struct):
        """A command implemented as a msgspec struct."""

        name: str
        count: int = 1

    # Test dataclass subcommand
    result = tyro.cli(
        as_callable(DataclassCommand | MsgspecCommand),
        args=["dataclass-command", "--value", "42"],
    )
    assert isinstance(result, DataclassCommand)
    assert result.value == 42
    assert result.flag is False

    # Test msgspec subcommand
    result = tyro.cli(
        as_callable(DataclassCommand | MsgspecCommand),
        args=["msgspec-command", "--name", "test"],
    )
    assert isinstance(result, MsgspecCommand)
    assert result.name == "test"
    assert result.count == 1

    # Verify helptext
    helptext = get_helptext_with_checks(as_callable(DataclassCommand | MsgspecCommand))
    assert "dataclass-command" in helptext
    assert "msgspec-command" in helptext
    assert "A command implemented as a dataclass" in helptext
    assert "A command implemented as a msgspec struct" in helptext


def test_msgspec_subcommands_with_enums():
    """Test msgspec subcommands with enum types."""

    class LogLevel(enum.Enum):
        DEBUG = "debug"
        INFO = "info"
        WARNING = "warning"
        ERROR = "error"

    class Configure(msgspec.Struct):
        """Configure application settings."""

        log_level: LogLevel = LogLevel.INFO
        verbose: bool = False

    class Run(msgspec.Struct):
        """Run the application."""

        log_level: LogLevel = LogLevel.INFO
        input_file: Optional[Path] = None

    # Test configure subcommand with enum
    result = tyro.cli(
        as_callable(Configure | Run), args=["configure", "--log-level", "DEBUG"]
    )
    assert isinstance(result, Configure)
    assert result.log_level == LogLevel.DEBUG
    assert result.verbose is False

    # Test run subcommand with enum
    result = tyro.cli(
        as_callable(Configure | Run),
        args=["run", "--log-level", "ERROR", "--input-file", "data.txt"],
    )
    assert isinstance(result, Run)
    assert result.log_level == LogLevel.ERROR
    assert result.input_file == Path("data.txt")

    # Test invalid enum value
    with pytest.raises(SystemExit):
        tyro.cli(
            as_callable(Configure | Run),
            args=["configure", "--log-level", "INVALID"],
        )
