"""Test TypeVar default support via typing_extensions and TyroWarning.

This test file works across all Python versions since it only uses
typing_extensions.TypeVar which has default support in all versions
when typing_extensions is installed.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Generic

import pytest
from typing_extensions import TypeVar

import tyro
from tyro._warnings import TyroWarning

# Test with TypeVar that has a default (via typing_extensions).
T_with_default = TypeVar("T_with_default", default=str)

# TypeVar without default.
T_no_default = TypeVar("T_no_default")

# TypeVar with bound.
T_with_bound = TypeVar("T_with_bound", bound=int)


@dataclass
class GenericWithDefault(Generic[T_with_default]):
    """Generic class with TypeVar that has a default."""

    value: T_with_default


@dataclass
class GenericNoDefault(Generic[T_no_default]):
    """Generic class with TypeVar that has no default."""

    value: T_no_default


@dataclass
class GenericWithBound(Generic[T_with_bound]):
    """Generic class with TypeVar that has a bound."""

    value: T_with_bound


def test_typevar_with_default_no_warning():
    """Test that TypeVar with default from typing_extensions doesn't produce warning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        @dataclass
        class Config(Generic[T_with_default]):
            value: T_with_default = "default"  # type: ignore

        # This should not produce a warning.
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


def test_typevar_no_default_produces_warning():
    """Test that TypeVar without default from typing_extensions produces TyroWarning."""
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


def test_typevar_with_bound_produces_warning():
    """Test that TypeVar with bound produces TyroWarning but uses bound."""
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


def test_tyro_warning_can_be_filtered():
    """Test that TyroWarning can be filtered using warnings.filterwarnings."""
    with warnings.catch_warnings(record=True) as w:
        # Filter out TyroWarning.
        warnings.filterwarnings("ignore", category=TyroWarning)

        @dataclass
        class Config(Generic[T_no_default]):
            value: T_no_default = "default"  # type: ignore

        # This would normally produce a warning, but it should be filtered.
        result = tyro.cli(Config, args=["--value", "test"], default=Config())

        # Check that no warnings were recorded.
        assert len(w) == 0, f"Warnings should have been filtered: {w}"
        assert result.value == "test"


def test_union_type_mismatch_uses_tyro_warning():
    """Test that union type mismatches use TyroWarning."""

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        @dataclass
        class Config:
            # This default doesn't match the union type.
            value: int | float = "not_a_number"  # type: ignore

        # This should produce a TyroWarning about type mismatch.
        result = tyro.cli(Config, args=["--value", "42"], default=Config())

        # Check that a TyroWarning was raised.
        tyro_warnings = [
            warning
            for warning in w
            if issubclass(warning.category, TyroWarning)
            and "does not match any type in Union" in str(warning.message)
        ]
        assert len(tyro_warnings) > 0, "Expected TyroWarning for union type mismatch"
        assert result.value == 42


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
