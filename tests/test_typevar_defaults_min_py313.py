"""Test TypeVar default support from Python 3.13's typing module.

This test file requires Python 3.13+ since it tests the native typing.TypeVar
default support introduced in PEP 696.
"""

from __future__ import annotations

import typing
import warnings
from dataclasses import dataclass
from typing import Generic

import pytest
from typing_extensions import TypeVar as ExtTypeVar

import tyro
from tyro._warnings import TyroWarning

T_ext = ExtTypeVar("T_ext", default=int)
T_typing = typing.TypeVar("T_typing", default=int)

# Python 3.13+ typing.TypeVar with default.
T_with_default = typing.TypeVar("T_with_default", default=str)
T_no_default = typing.TypeVar("T_no_default")
T_with_bound = typing.TypeVar("T_with_bound", bound=int)


@dataclass
class GenericWithDefault(Generic[T_with_default]):
    """Generic class with typing.TypeVar that has a default."""

    value: T_with_default


@dataclass
class GenericNoDefault(Generic[T_no_default]):
    """Generic class with typing.TypeVar that has no default."""

    value: T_no_default


@dataclass
class GenericWithBound(Generic[T_with_bound]):
    """Generic class with typing.TypeVar that has a bound."""

    value: T_with_bound


def test_typing_typevar_with_default_no_warning():
    """Test that typing.TypeVar with default (Python 3.13+) doesn't produce warning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        @dataclass
        class Config(Generic[T_with_default]):
            value: T_with_default = "default"  # type: ignore

        # This should not produce a warning in Python 3.13+.
        result = tyro.cli(Config, args=["--value", "test"], default=Config())

        # Check no TyroWarning was raised for TypeVar resolution.
        tyro_warnings = [
            warning
            for warning in w
            if issubclass(warning.category, TyroWarning)
            and "Could not resolve type parameter" in str(warning.message)
        ]
        assert len(tyro_warnings) == 0, f"Unexpected TypeVar warnings: {tyro_warnings}"
        assert result.value == "test"


def test_typing_typevar_no_default_produces_warning():
    """Test that typing.TypeVar without default produces TyroWarning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        @dataclass
        class Config(Generic[T_no_default]):
            value: T_no_default = "default"  # type: ignore

        # This should produce a warning.
        result = tyro.cli(Config, args=["--value", "test"], default=Config())

        # Check that a TyroWarning was raised.
        tyro_warnings = [
            warning
            for warning in w
            if issubclass(warning.category, TyroWarning)
            and "Could not resolve type parameter" in str(warning.message)
        ]
        assert len(tyro_warnings) > 0, "Expected TyroWarning for unresolved TypeVar"
        assert result.value == "test"


def test_typing_typevar_with_bound_produces_warning():
    """Test that typing.TypeVar with bound produces TyroWarning but uses bound."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        @dataclass
        class Config(Generic[T_with_bound]):
            value: T_with_bound = 42  # type: ignore

        # This should produce a warning but use the bound type.
        result = tyro.cli(Config, args=["--value", "100"], default=Config())

        # Check that a TyroWarning was raised.
        tyro_warnings = [
            warning
            for warning in w
            if issubclass(warning.category, TyroWarning)
            and "Could not resolve type parameter" in str(warning.message)
        ]
        assert len(tyro_warnings) > 0, "Expected TyroWarning for TypeVar with bound"
        assert result.value == 100


def test_both_typing_and_typing_extensions_work():
    """Verify that both typing.TypeVar and typing_extensions.TypeVar work with defaults."""

    @dataclass
    class ConfigExt(Generic[T_ext]):
        value: T_ext = 42  # type: ignore

    @dataclass
    class ConfigTyping(Generic[T_typing]):
        value: T_typing = 42  # type: ignore

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Both should work without warnings.
        result_ext = tyro.cli(ConfigExt, args=["--value", "100"], default=ConfigExt())
        result_typing = tyro.cli(
            ConfigTyping, args=["--value", "200"], default=ConfigTyping()
        )

        # Check no TypeVar warnings were raised.
        tyro_warnings = [
            warning
            for warning in w
            if issubclass(warning.category, TyroWarning)
            and "Could not resolve type parameter" in str(warning.message)
        ]
        assert len(tyro_warnings) == 0, f"Unexpected TypeVar warnings: {tyro_warnings}"
        assert result_ext.value == 100
        assert result_typing.value == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
