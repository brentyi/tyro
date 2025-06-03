"""Test union types with config parameters."""

from __future__ import annotations

import dataclasses
from typing import Union

import pytest

import tyro


@dataclasses.dataclass
class Command1:
    """First command."""

    arg1: str
    flag1: bool = False


@dataclasses.dataclass
class Command2:
    """Second command."""

    arg2: int
    flag2: bool = True


@dataclasses.dataclass
class NestedConfig:
    """Nested config class."""

    value: float = 1.0


@dataclasses.dataclass
class Command3:
    """Third command with nested config."""

    nested: NestedConfig
    name: str = "default"


def test_union_with_empty_config():
    """Union types should work with empty config tuple."""
    # Python 3.8 compatible syntax
    result = tyro.cli(
        Union[Command1, Command2], args=["command1", "--arg1", "test"], config=()
    )
    assert result == Command1(arg1="test", flag1=False)


def test_union_with_flag_create_pairs_off():
    """Union types should work with FlagCreatePairsOff config."""
    result = tyro.cli(
        Union[Command1, Command2],
        args=["command1", "--arg1", "test", "--flag1"],
        config=(tyro.conf.FlagCreatePairsOff,),
    )
    assert result == Command1(arg1="test", flag1=True)


def test_union_with_flag_conversion_off():
    """Union types should work with FlagConversionOff config."""
    result = tyro.cli(
        Union[Command1, Command2],
        args=["command2", "--arg2", "42", "--flag2", "False"],
        config=(tyro.conf.FlagConversionOff,),
    )
    assert result == Command2(arg2=42, flag2=False)


def test_union_with_multiple_configs():
    """Union types should work with multiple config options."""
    result = tyro.cli(
        Union[Command1, Command2],
        args=["command2", "--arg2", "42", "--flag2", "True"],
        config=(tyro.conf.FlagConversionOff,),
    )
    assert result == Command2(arg2=42, flag2=True)


def test_union_with_omit_subcommand_prefixes():
    """Union types should work with OmitSubcommandPrefixes."""
    result = tyro.cli(
        Union[Command1, Command2],
        args=["command1", "--arg1", "test"],
        config=(tyro.conf.OmitSubcommandPrefixes,),
    )
    assert result == Command1(arg1="test", flag1=False)


def test_union_with_positional_required_args():
    """Union types should work with PositionalRequiredArgs."""

    @dataclasses.dataclass
    class SimpleCmd1:
        required_arg: str

    @dataclasses.dataclass
    class SimpleCmd2:
        required_num: int

    result = tyro.cli(
        Union[SimpleCmd1, SimpleCmd2],
        args=["simple-cmd1", "hello"],
        config=(tyro.conf.PositionalRequiredArgs,),
    )
    assert result == SimpleCmd1(required_arg="hello")


def test_nested_union_with_config():
    """Nested union types should work with config."""
    result = tyro.cli(
        Union[Command1, Command3],
        args=["command3", "--nested.value", "2.5", "--name", "test"],
        config=(tyro.conf.FlagCreatePairsOff,),
    )
    assert result == Command3(nested=NestedConfig(value=2.5), name="test")


# Test Python 3.10+ union syntax if available (but fallback gracefully)
try:
    # This will only work in Python 3.10+
    exec("""
def test_modern_union_syntax_with_config():
    '''Test | syntax with config (Python 3.10+ only).'''
    result = tyro.cli(
        Command1 | Command2,
        args=["command1", "--arg1", "modern"],
        config=(tyro.conf.FlagCreatePairsOff,)
    )
    assert result == Command1(arg1="modern", flag1=False)
""")
except SyntaxError:
    # Python 3.8/3.9 - skip this test
    pass


def test_union_subcommand_help():
    """Test that help text works correctly with union types and config."""
    # This should not raise an exception
    with pytest.raises(SystemExit):
        tyro.cli(
            Union[Command1, Command2],
            args=["--help"],
            config=(tyro.conf.FlagCreatePairsOff,),
        )


def test_union_subcommand_specific_help():
    """Test that subcommand-specific help works with config."""
    # This should not raise an exception
    with pytest.raises(SystemExit):
        tyro.cli(
            Union[Command1, Command2],
            args=["command1", "--help"],
            config=(tyro.conf.FlagCreatePairsOff,),
        )


if __name__ == "__main__":
    # Run a few basic tests manually
    test_union_with_empty_config()
    test_union_with_flag_create_pairs_off()
    test_union_with_flag_conversion_off()
    print("All manual tests passed!")
