"""Tests for add_help parameter functionality."""

import dataclasses
import io
import sys

import pytest

import tyro


@dataclasses.dataclass
class SimpleConfig:
    """A simple configuration class."""

    value: int
    name: str = "default"


def simple_function(x: int, y: str = "hello") -> str:
    """A simple function for testing."""
    return f"{x}:{y}"


def test_cli_add_help_false():
    """Test that add_help=False prevents help from being added."""
    # Should raise an error when --help is provided with add_help=False
    with pytest.raises(SystemExit) as excinfo:
        tyro.cli(SimpleConfig, args=["--help"], add_help=False)
    assert excinfo.value.code == 2  # Should fail with parsing error, not help display


def test_cli_add_help_true():
    """Test that add_help=True (default) allows help."""
    # Should show help and exit with code 0
    with pytest.raises(SystemExit) as excinfo:
        # Redirect stdout to capture help output
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            tyro.cli(SimpleConfig, args=["--help"], add_help=True)
        finally:
            sys.stdout = old_stdout
    assert excinfo.value.code == 0  # Should exit cleanly after showing help


def test_cli_default_add_help():
    """Test that add_help defaults to True."""
    # Should show help and exit with code 0
    with pytest.raises(SystemExit) as excinfo:
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            tyro.cli(SimpleConfig, args=["--help"])
        finally:
            sys.stdout = old_stdout
    assert excinfo.value.code == 0


def test_get_parser_add_help_false():
    """Test that get_parser with add_help=False doesn't add help option."""
    parser = tyro.extras.get_parser(SimpleConfig, add_help=False)
    assert "-h" not in parser._option_string_actions
    assert "--help" not in parser._option_string_actions


def test_get_parser_add_help_true():
    """Test that get_parser with add_help=True adds help option."""
    parser = tyro.extras.get_parser(SimpleConfig, add_help=True)
    assert (
        "-h" in parser._option_string_actions
        or "--help" in parser._option_string_actions
    )


def test_get_parser_default_add_help():
    """Test that get_parser defaults to add_help=True."""
    parser = tyro.extras.get_parser(SimpleConfig)
    assert (
        "-h" in parser._option_string_actions
        or "--help" in parser._option_string_actions
    )


def test_function_cli_add_help():
    """Test add_help works with function targets."""
    # Test with add_help=False
    result = tyro.cli(simple_function, args=["--x", "42"], add_help=False)
    assert result == "42:hello"

    # Test that --help fails with add_help=False
    with pytest.raises(SystemExit) as excinfo:
        tyro.cli(simple_function, args=["--help"], add_help=False)
    assert excinfo.value.code == 2


def test_subcommand_app_add_help():
    """Test add_help parameter with SubcommandApp."""
    from tyro.extras import SubcommandApp

    app = SubcommandApp()

    @app.command
    def cmd1(x: int) -> int:
        return x

    @app.command
    def cmd2(y: str) -> str:
        return y

    # Test with add_help=False
    result = app.cli(args=["cmd1", "--x", "5"], add_help=False)
    assert result == 5

    # Test that --help fails with add_help=False
    with pytest.raises(SystemExit) as excinfo:
        app.cli(args=["--help"], add_help=False)
    assert excinfo.value.code == 2


def test_subcommand_cli_from_dict_add_help():
    """Test add_help parameter with subcommand_cli_from_dict."""

    def cmd1(x: int) -> int:
        return x * 2

    def cmd2(y: str) -> str:
        return y.upper()

    subcommands = {"multiply": cmd1, "uppercase": cmd2}

    # Test with add_help=False
    result = tyro.extras.subcommand_cli_from_dict(
        subcommands, args=["multiply", "--x", "3"], add_help=False
    )
    assert result == 6

    # Test that --help fails with add_help=False
    with pytest.raises(SystemExit) as excinfo:
        tyro.extras.subcommand_cli_from_dict(
            subcommands, args=["--help"], add_help=False
        )
    assert excinfo.value.code == 2


def test_overridable_config_cli_add_help():
    """Test add_help parameter with overridable_config_cli."""

    @dataclasses.dataclass
    class Config:
        a: int
        b: str

    configs = {
        "small": ("Small config", Config(1, "small")),
        "big": ("Big config", Config(100, "big")),
    }

    # Test with add_help=False
    result = tyro.extras.overridable_config_cli(configs, args=["small"], add_help=False)
    assert result.a == 1
    assert result.b == "small"

    # Test that --help fails with add_help=False
    with pytest.raises(SystemExit) as excinfo:
        tyro.extras.overridable_config_cli(configs, args=["--help"], add_help=False)
    assert excinfo.value.code == 2


def test_return_unknown_args_with_add_help_false():
    """Test that --help/-h are returned as unknown args when add_help=False and return_unknown_args=True."""

    @dataclasses.dataclass
    class Config:
        value: int = 5

    # Test that --help is returned in unknown args
    result, unknown = tyro.cli(
        Config, args=["--help"], add_help=False, return_unknown_args=True
    )
    assert unknown == ["--help"]
    assert result.value == 5

    # Test that -h is returned in unknown args
    result, unknown = tyro.cli(
        Config, args=["-h"], add_help=False, return_unknown_args=True
    )
    assert unknown == ["-h"]
    assert result.value == 5

    # Test with both --help and other unknown args
    result, unknown = tyro.cli(
        Config,
        args=["--help", "--unknown", "arg"],
        add_help=False,
        return_unknown_args=True,
    )
    assert "--help" in unknown
    assert "--unknown" in unknown
    assert "arg" in unknown
    assert result.value == 5

    # Test that with add_help=True, --help still shows help (doesn't return unknown args)
    with pytest.raises(SystemExit) as excinfo:
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            tyro.cli(Config, args=["--help"], add_help=True, return_unknown_args=True)
        finally:
            sys.stdout = old_stdout
    assert excinfo.value.code == 0  # Should exit cleanly after showing help
