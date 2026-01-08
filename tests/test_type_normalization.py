"""Tests for type normalization via NormalizedType.

Tests cover:
- Basic type normalization for primitives and classes
- Generic type normalization (List, Dict, Tuple, etc.)
- Union type handling
- Annotated type handling with markers and metadata
- Marker inheritance via inherit_markers parameter
- Re-normalization of type arguments
- Edge cases and integration with FieldDefinition
"""

from __future__ import annotations

import dataclasses
from typing import Callable, Dict, List, Literal, Optional, Set, Tuple, Union

import pytest
from typing_extensions import Annotated

import tyro
from tyro._normalized_type import NormalizedType
from tyro.conf import Positional, UseAppendAction

# =============================================================================
# Basic normalization tests
# =============================================================================


def test_normalize_int():
    """Simple int type normalizes correctly."""
    normalized = NormalizedType.from_type(int)
    assert normalized.type is int
    assert normalized.type_origin is None
    assert normalized.type_args is None
    assert len(normalized.markers) == 0
    assert normalized.metadata == ()


def test_normalize_str():
    """Simple str type normalizes correctly."""
    normalized = NormalizedType.from_type(str)
    assert normalized.type is str
    assert normalized.type_origin is None
    assert normalized.type_args is None


def test_normalize_bool():
    """Simple bool type normalizes correctly."""
    normalized = NormalizedType.from_type(bool)
    assert normalized.type is bool
    assert normalized.type_origin is None
    assert normalized.type_args is None


def test_normalize_float():
    """Simple float type normalizes correctly."""
    normalized = NormalizedType.from_type(float)
    assert normalized.type is float
    assert normalized.type_origin is None
    assert normalized.type_args is None


def test_normalize_none():
    """Simple None type normalizes correctly."""
    normalized = NormalizedType.from_type(type(None))
    assert normalized.type is type(None)
    assert normalized.type_origin is None
    assert normalized.type_args is None


def test_normalize_dataclass():
    """Custom dataclass normalizes correctly."""

    @dataclasses.dataclass
    class Config:
        x: int
        y: str

    normalized = NormalizedType.from_type(Config)
    assert normalized.type is Config
    assert normalized.type_origin is None
    assert normalized.type_args is None
    assert len(normalized.markers) == 0


def test_normalize_regular_class():
    """Regular class normalizes correctly."""

    class MyClass:
        pass

    normalized = NormalizedType.from_type(MyClass)
    assert normalized.type is MyClass
    assert normalized.type_origin is None
    assert normalized.type_args is None


# =============================================================================
# Generic type tests
# =============================================================================


def test_normalize_list_int():
    """list[int] normalizes with type_args."""
    normalized = NormalizedType.from_type(List[int])
    assert normalized.type_origin is list
    assert normalized.type_args is not None
    assert len(normalized.type_args) == 1
    assert normalized.type_args[0].type is int


def test_normalize_dict_str_int():
    """dict[str, int] normalizes with type_args."""
    normalized = NormalizedType.from_type(Dict[str, int])
    assert normalized.type_origin is dict
    assert normalized.type_args is not None
    assert len(normalized.type_args) == 2
    assert normalized.type_args[0].type is str
    assert normalized.type_args[1].type is int


def test_normalize_tuple_int_str():
    """tuple[int, str] normalizes with type_args."""
    normalized = NormalizedType.from_type(Tuple[int, str])
    assert normalized.type_origin is tuple
    assert normalized.type_args is not None
    assert len(normalized.type_args) == 2
    assert normalized.type_args[0].type is int
    assert normalized.type_args[1].type is str


def test_normalize_set_float():
    """set[float] normalizes with type_args."""
    normalized = NormalizedType.from_type(Set[float])
    assert normalized.type_origin is set
    assert normalized.type_args is not None
    assert len(normalized.type_args) == 1
    assert normalized.type_args[0].type is float


# =============================================================================
# Union type tests
# =============================================================================


def test_normalize_union_int_str():
    """Union[int, str] normalizes correctly."""
    import types

    normalized = NormalizedType.from_type(Union[int, str])
    # type_origin is Union for typing.Union, or UnionType for int | str syntax.
    assert normalized.type_origin is Union or normalized.type_origin is types.UnionType
    assert normalized.type_args is not None
    assert len(normalized.type_args) == 2
    assert normalized.type_args[0].type is int
    assert normalized.type_args[1].type is str


def test_normalize_optional_int():
    """Optional[int] normalizes correctly."""
    normalized = NormalizedType.from_type(Optional[int])
    assert normalized.type_origin is Union
    assert normalized.type_args is not None
    assert len(normalized.type_args) == 2


@pytest.mark.skipif(
    __import__("sys").version_info < (3, 10),
    reason="Pipe union syntax requires Python 3.10+",
)
def test_normalize_pipe_union():
    """int | str normalizes correctly (Python 3.10+)."""
    normalized = NormalizedType.from_type(int | str)
    assert normalized.type_args is not None
    assert len(normalized.type_args) == 2


# =============================================================================
# Annotated handling tests
# =============================================================================


def test_annotated_with_marker():
    """Annotated with a marker extracts correctly."""
    normalized = NormalizedType.from_type(Annotated[int, Positional])
    assert normalized.type is int
    assert Positional in normalized.markers
    assert len(normalized.metadata) == 0  # Positional is a marker.


def test_annotated_with_multiple_markers():
    """Annotated with multiple markers extracts all."""
    normalized = NormalizedType.from_type(Annotated[int, Positional, UseAppendAction])
    assert normalized.type is int
    assert Positional in normalized.markers
    assert UseAppendAction in normalized.markers
    assert len(normalized.markers) == 2


def test_annotated_with_metadata():
    """Annotated with non-marker metadata extracts correctly."""
    normalized = NormalizedType.from_type(Annotated[int, "some_metadata"])
    assert normalized.type is int
    assert len(normalized.markers) == 0
    assert "some_metadata" in normalized.metadata


def test_annotated_with_mixed():
    """Annotated with both markers and metadata extracts correctly."""
    normalized = NormalizedType.from_type(Annotated[int, Positional, "metadata"])
    assert normalized.type is int
    assert Positional in normalized.markers
    assert "metadata" in normalized.metadata


# =============================================================================
# Type argument tests
# =============================================================================


def test_type_args_none_for_non_generic():
    """type_args is None for non-generic types."""
    normalized = NormalizedType.from_type(int)
    assert normalized.type_args is None


def test_type_args_contains_normalized_type():
    """type_args contains NormalizedType instances."""
    normalized = NormalizedType.from_type(List[int])
    assert normalized.type_args is not None
    assert all(isinstance(arg, NormalizedType) for arg in normalized.type_args)


def test_raw_type_args_property():
    """raw_type_args property returns original un-normalized args."""
    normalized = NormalizedType.from_type(List[int])
    assert normalized.raw_type_args == (int,)


def test_raw_type_args_empty_for_non_generic():
    """raw_type_args returns empty tuple for non-generic types."""
    normalized = NormalizedType.from_type(int)
    assert normalized.raw_type_args == ()


# =============================================================================
# Marker inheritance tests
# =============================================================================


def test_inherit_single_marker():
    """inherit_markers makes marker appear in nested normalizations."""
    normalized = NormalizedType.from_type(int, inherit_markers=(Positional,))
    assert Positional in normalized.markers


def test_inherit_multiple_markers():
    """inherit_markers can pass multiple markers."""
    normalized = NormalizedType.from_type(
        int, inherit_markers=(Positional, UseAppendAction)
    )
    assert Positional in normalized.markers
    assert UseAppendAction in normalized.markers


def test_markers_combine():
    """Inherited + extracted markers are combined."""
    normalized = NormalizedType.from_type(
        Annotated[int, UseAppendAction], inherit_markers=(Positional,)
    )
    assert Positional in normalized.markers
    assert UseAppendAction in normalized.markers


def test_markers_as_set():
    """markers can be converted to set."""
    normalized = NormalizedType.from_type(Annotated[int, Positional])
    markers_set = set(normalized.markers)
    assert isinstance(markers_set, set)
    assert Positional in markers_set


def test_marker_presence():
    """Check marker presence using 'in' operator."""
    normalized = NormalizedType.from_type(Annotated[int, Positional])
    assert Positional in normalized.markers
    assert UseAppendAction not in normalized.markers


def test_filter_markers():
    """Markers are immutable tuples; filter to exclude markers."""
    normalized = NormalizedType.from_type(Annotated[int, Positional])
    new_markers = tuple(m for m in normalized.markers if m != Positional)
    assert Positional not in new_markers
    # Original unchanged.
    assert Positional in normalized.markers


def test_multiple_inherited_markers():
    """Multiple inherited markers are combined."""
    normalized = NormalizedType.from_type(
        int, inherit_markers=(Positional, UseAppendAction)
    )
    assert Positional in normalized.markers
    assert UseAppendAction in normalized.markers


# =============================================================================
# Re-normalization tests
# =============================================================================


def test_renormalize_args_without_marker():
    """renormalize_args_without_marker() excludes marker from type_args."""
    normalized = NormalizedType.from_type(List[int], inherit_markers=(Positional,))
    # type_args should have Positional.
    assert normalized.type_args is not None
    assert Positional in normalized.type_args[0].markers

    # Re-normalize without Positional.
    new_normalized = normalized.renormalize_args_without_marker(Positional)
    assert new_normalized.type_args is not None
    assert Positional not in new_normalized.type_args[0].markers


def test_renormalize_immutability():
    """Original NormalizedType unchanged after renormalize."""
    normalized = NormalizedType.from_type(List[int], inherit_markers=(Positional,))
    new_normalized = normalized.renormalize_args_without_marker(Positional)
    # Original still has Positional in type_args.
    assert Positional in normalized.type_args[0].markers
    assert Positional not in new_normalized.type_args[0].markers


# =============================================================================
# Edge case tests
# =============================================================================


def test_nested_annotated():
    """Nested Annotated - both layers stripped."""
    inner = Annotated[int, Positional]
    outer = Annotated[inner, UseAppendAction]
    normalized = NormalizedType.from_type(outer)
    # Outer layer stripped: UseAppendAction extracted.
    assert UseAppendAction in normalized.markers
    # Both layers are stripped by unwrap_annotated.
    assert normalized.type is int


def test_union_with_different_markers_per_branch():
    """Union types with different markers per branch."""
    union_type = Union[Annotated[int, Positional], Annotated[str, UseAppendAction]]
    normalized = NormalizedType.from_type(union_type)
    assert normalized.type_origin is Union
    assert normalized.type_args is not None
    # Each branch has its own markers.
    assert Positional in normalized.type_args[0].markers
    assert UseAppendAction in normalized.type_args[1].markers


def test_callable_type():
    """Callable types normalize correctly."""
    normalized = NormalizedType.from_type(Callable[[int, str], bool])
    assert normalized.type_origin is not None  # Callable origin.
    assert normalized.type_args is not None


def test_deeply_nested_generics():
    """Deeply nested generics normalize correctly."""
    deep_type = List[Dict[str, Tuple[int, ...]]]
    normalized = NormalizedType.from_type(deep_type)
    assert normalized.type_origin is list
    assert normalized.type_args is not None
    dict_arg = normalized.type_args[0]
    assert dict_arg.type_origin is dict


def test_literal_type():
    """Literal types normalize correctly."""
    normalized = NormalizedType.from_type(Literal["a", "b", "c"])
    assert normalized.type_origin is Literal


# =============================================================================
# Integration tests with FieldDefinition
# =============================================================================


def test_field_inherits_markers():
    """FieldDefinition picks up markers from inherit_markers parameter."""
    from tyro._fields import FieldDefinition

    field = FieldDefinition.make(
        name="test",
        typ=int,
        default=0,
        helptext=None,
        inherit_markers=(Positional,),
    )
    assert Positional in field.norm_type.markers


def test_field_combines_markers():
    """FieldDefinition combines inherited and Annotated markers."""
    from tyro._fields import FieldDefinition

    field = FieldDefinition.make(
        name="test",
        typ=Annotated[int, UseAppendAction],
        default=0,
        helptext=None,
        inherit_markers=(Positional,),
    )
    assert Positional in field.norm_type.markers
    assert UseAppendAction in field.norm_type.markers


# =============================================================================
# Integration tests with tyro.cli
# =============================================================================


@dataclasses.dataclass
class _PositionalConfig:
    x: Annotated[int, Positional]


@dataclasses.dataclass
class _NestedInner:
    value: int


@dataclasses.dataclass
class _NestedOuter:
    inner: _NestedInner


def test_cli_annotated_positional():
    """Annotated positional argument works."""
    result = tyro.cli(_PositionalConfig, args=["42"])
    assert result.x == 42


def test_cli_nested_struct():
    """Nested struct types work correctly."""
    result = tyro.cli(_NestedOuter, args=["--inner.value", "10"])
    assert result.inner.value == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
