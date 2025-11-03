"""Tests for Python eval-based collections.

These tests verify that tyro can parse collections using Python syntax
(e.g., "[128, 128, 128]", "{'a': 1}") via eval() when the
UsePythonSyntaxForCollections marker is used.

The eval() approach supports both literal values and non-literal types like
pathlib.Path by making common types available in a secure eval() context.

This is particularly useful for wandb sweeps integration.
"""

from dataclasses import dataclass

import pytest

import tyro


def test_tuple_python_syntax():
    """Test that Python literal syntax works for tuples."""

    @dataclass
    class Config:
        dims: tuple[int, int, int]

    # Normal usage without marker.
    assert tyro.cli(Config, args=["--dims", "1", "2", "3"]) == Config(dims=(1, 2, 3))

    # With UsePythonSyntaxForCollections marker.
    assert tyro.cli(
        Config,
        args=["--dims", "(1, 2, 3)"],
        config=(tyro.conf.UsePythonSyntaxForCollections,),
    ) == Config(dims=(1, 2, 3))


def test_tuple_strings():
    """Test Python syntax for tuples with string elements."""

    @dataclass
    class Config:
        names: tuple[str, str]

    assert tyro.cli(
        Config,
        args=["--names", "('foo', 'bar')"],
        config=(tyro.conf.UsePythonSyntaxForCollections,),
    ) == Config(names=("foo", "bar"))


def test_list_python_syntax():
    """Test Python syntax for lists."""

    @dataclass
    class Config:
        values: list[int]

    # Normal usage without marker.
    assert tyro.cli(Config, args=["--values", "1", "2", "3"]) == Config(
        values=[1, 2, 3]
    )

    # With UsePythonSyntaxForCollections marker.
    assert tyro.cli(
        Config,
        args=["--values", "[1, 2, 3]"],
        config=(tyro.conf.UsePythonSyntaxForCollections,),
    ) == Config(values=[1, 2, 3])


def test_dict_python_syntax():
    """Test Python syntax for dicts."""

    @dataclass
    class Config:
        mapping: dict[str, int]

    # Normal usage without marker.
    result = tyro.cli(Config, args=["--mapping", "a", "1", "b", "2"])
    assert result == Config(mapping={"a": 1, "b": 2})

    # With UsePythonSyntaxForCollections marker.
    result = tyro.cli(
        Config,
        args=["--mapping", "{'a': 1, 'b': 2}"],
        config=(tyro.conf.UsePythonSyntaxForCollections,),
    )
    assert result == Config(mapping={"a": 1, "b": 2})


def test_set_python_syntax():
    """Test Python syntax for sets."""

    @dataclass
    class Config:
        values: set[int]

    result = tyro.cli(
        Config,
        args=["--values", "{1, 2, 3}"],
        config=(tyro.conf.UsePythonSyntaxForCollections,),
    )
    assert result == Config(values={1, 2, 3})


def test_nested_structure():
    """Test nested structures with Python syntax."""

    @dataclass
    class Inner:
        size: tuple[int, int]

    @dataclass
    class Outer:
        inner: Inner

    result = tyro.cli(
        Outer,
        args=["--inner.size", "(100, 200)"],
        config=(tyro.conf.UsePythonSyntaxForCollections,),
    )
    assert result == Outer(inner=Inner(size=(100, 200)))


def test_mixed_types():
    """Test tuple with mixed numeric types."""

    @dataclass
    class Config:
        mixed: tuple[int, float, int]

    result = tyro.cli(
        Config,
        args=["--mixed", "(1, 2.5, 3)"],
        config=(tyro.conf.UsePythonSyntaxForCollections,),
    )
    assert result == Config(mixed=(1, 2.5, 3))


def test_invalid_python_syntax():
    """Test that invalid Python syntax raises an error."""

    @dataclass
    class Config:
        values: list[int]

    with pytest.raises(SystemExit):
        tyro.cli(
            Config,
            args=["--values", "[1, 2, "],
            config=(tyro.conf.UsePythonSyntaxForCollections,),
        )


def test_type_mismatch():
    """Test that type mismatches raise an error."""

    @dataclass
    class Config:
        values: tuple[int, int]

    # Passing a list when expecting a tuple.
    with pytest.raises(SystemExit):
        tyro.cli(
            Config,
            args=["--values", "[1, 2]"],
            config=(tyro.conf.UsePythonSyntaxForCollections,),
        )


def test_helptext_coverage():
    """Test helptext generation to cover str_from_instance."""
    import sys
    from dataclasses import field

    @dataclass
    class Config:
        simple: list[int] = field(default_factory=lambda: [1, 2, 3])
        nested: list[tuple[int, str]] = field(
            default_factory=lambda: [(1, "a"), (2, "b")]
        )

    # Getting helptext will call str_from_instance for defaults.
    sys.argv = ["test", "--help"]
    with pytest.raises(SystemExit):
        tyro.cli(Config, config=(tyro.conf.UsePythonSyntaxForCollections,))


def test_union_with_default():
    """Test union types with defaults to cover is_instance_fn."""
    import sys

    @dataclass
    class Config:
        value: tuple[int, ...] | int = 3

    # Getting helptext with a union default exercises is_instance.
    sys.argv = ["test", "--help"]
    with pytest.raises(SystemExit):
        tyro.cli(Config, config=(tyro.conf.UsePythonSyntaxForCollections,))


def test_variable_length_tuple():
    """Test variable-length tuples."""

    @dataclass
    class Config:
        values: tuple[int, ...]

    result = tyro.cli(
        Config,
        args=["--values", "(1, 2, 3, 4, 5)"],
        config=(tyro.conf.UsePythonSyntaxForCollections,),
    )
    assert result == Config(values=(1, 2, 3, 4, 5))


def test_nested_union_metavar():
    """Test metavar generation for nested union types to cover edge cases."""
    import sys
    from typing import Union

    @dataclass
    class Config:
        # This will exercise the metavar generation with Union types.
        values: list[Union[int, str]]

    # Getting helptext will generate metavar for the type.
    sys.argv = ["test", "--help"]
    with pytest.raises(SystemExit):
        tyro.cli(Config, config=(tyro.conf.UsePythonSyntaxForCollections,))


def test_nested_literal_metavar():
    """Test metavar generation for Literal types (which lack __name__)."""
    import sys
    from typing import Literal

    @dataclass
    class Config:
        # Literal types don't have __name__, testing edge case in metavar generation.
        values: list[Literal["a", "b"]]

    # Getting helptext will generate metavar for the type.
    sys.argv = ["test", "--help"]
    with pytest.raises(SystemExit):
        tyro.cli(Config, config=(tyro.conf.UsePythonSyntaxForCollections,))


def test_pathlib_support():
    """Test that non-builtin types like Path work with eval()."""
    from pathlib import Path

    @dataclass
    class Config:
        paths: list[Path]

    result = tyro.cli(
        Config,
        args=["--paths", "[Path('foo'), Path('bar')]"],
        config=(tyro.conf.UsePythonSyntaxForCollections,),
    )
    assert result == Config(paths=[Path("foo"), Path("bar")])


def test_unparameterized_generic_fallback():
    """Test that unparameterized generics fall back to other rules."""
    # When a collection type has no type args, the eval rule should return None
    # and let other rules handle it. typing.List without subscript has origin=list
    # but no args, which triggers this early return path.
    from typing import List

    @dataclass
    class Config:
        # Using unparameterized typing.List triggers the early return.
        # It will be handled by other rules as a list with inferred type.
        values: List = None  # type: ignore

    # This should work - the eval rule returns None, other rules handle it.
    result = tyro.cli(
        Config,
        args=[],
        config=(tyro.conf.UsePythonSyntaxForCollections,),
    )
    assert result.values is None
