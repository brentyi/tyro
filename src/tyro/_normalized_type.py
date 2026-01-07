"""Centralized type normalization for tyro.

This module provides `NormalizedType`, which encapsulates a normalized type
with its origin, type arguments, markers, and metadata. It centralizes the
type normalization logic that was previously scattered across the codebase.
"""

from __future__ import annotations

import contextvars
import dataclasses
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from typing_extensions import get_args, get_origin

from . import _resolver
from ._typing import TypeForm
from .conf import _markers

# Context variable for marker inheritance.
_inherited_markers: contextvars.ContextVar[tuple[Any, ...]] = contextvars.ContextVar(
    "_inherited_markers", default=()
)


@dataclasses.dataclass(frozen=True)
class NormalizedType:
    """A normalized type with extracted metadata and markers.

    This class encapsulates a type that has been normalized by stripping one
    layer of `typing.Annotated` and extracting markers and metadata. The
    `type_args` are recursively normalized with inherited markers.

    Attributes:
        type: The type after stripping one layer of Annotated. May still
            contain nested Annotated types.
        type_origin: The result of `get_origin(type)`, or None for non-generic types.
        type_args: Pre-normalized type arguments with inherited markers.
            None if the type has no type arguments.
        markers: Tuple of tyro markers extracted from the type annotation,
            combined with inherited markers from context.
        metadata: Tuple of all non-marker metadata from the Annotated type.
    """

    type: TypeForm[Any] | Callable
    type_origin: Any | None
    type_args: tuple[NormalizedType, ...] | None
    markers: tuple[Any, ...]
    metadata: tuple[Any, ...]
    _raw_type_args: tuple[Any, ...] | None = dataclasses.field(
        default=None, repr=False, compare=False
    )

    @staticmethod
    @contextmanager
    def inherit(*markers: Any) -> Iterator[None]:
        """Context manager for implicit marker inheritance.

        All `NormalizedType.normalize()` calls within this context will
        include the specified markers in addition to any markers already
        being inherited.

        Example::

            with NormalizedType.inherit(SomeMarker):
                # All normalize() calls here will include SomeMarker
                normalized = NormalizedType.normalize(some_type)
                assert SomeMarker in normalized.markers

        Args:
            markers: Markers to inherit in the context.
        """
        current = _inherited_markers.get()
        token = _inherited_markers.set(current + markers)
        try:
            yield
        finally:
            _inherited_markers.reset(token)

    @property
    def raw_type_args(self) -> tuple[Any, ...]:
        """Get the raw (un-normalized) type arguments.

        This is useful when you need to re-normalize type arguments with
        different markers (e.g., stripping UseAppendAction for inner types).

        Returns:
            The raw type arguments, or an empty tuple if there are none.
        """
        if self._raw_type_args is not None:
            return self._raw_type_args
        return ()

    @staticmethod
    def normalize(raw_type: TypeForm[Any] | Callable) -> NormalizedType:
        """Normalize a type by stripping one layer of Annotated.

        This method:
        1. Strips one layer of `typing.Annotated` from the type
        2. Extracts markers and metadata from the annotation
        3. Combines extracted markers with inherited markers from context
        4. Recursively normalizes type arguments with the combined markers

        Args:
            raw_type: The raw type to normalize.

        Returns:
            A NormalizedType instance with the normalized type information.
        """
        # Get inherited markers from context.
        inherited = _inherited_markers.get()

        # Extract markers from the type annotation.
        typ, extra_markers = _resolver.unwrap_annotated(
            raw_type, search_type=_markers._Marker
        )

        # Get all metadata (not just markers).
        _, all_metadata = _resolver.unwrap_annotated(raw_type, search_type="all")

        # Combine inherited and extracted markers.
        markers = inherited + tuple(extra_markers)

        # Extract non-marker metadata.
        metadata = tuple(m for m in all_metadata if not isinstance(m, _markers._Marker))

        # Get origin and raw type args.
        type_origin = get_origin(typ)
        raw_args = get_args(typ)

        # Recursively normalize type arguments with inherited markers.
        # We set the context directly rather than using inherit() to avoid
        # stacking markers (inherit() adds to the current context, but we
        # want to replace it with the combined markers).
        if raw_args:
            token = _inherited_markers.set(markers)
            try:
                type_args = tuple(NormalizedType.normalize(arg) for arg in raw_args)
            finally:
                _inherited_markers.reset(token)
        else:
            type_args = None

        return NormalizedType(
            type=typ,
            type_origin=type_origin,
            type_args=type_args,
            markers=markers,
            metadata=metadata,
            _raw_type_args=raw_args if raw_args else None,
        )

    def has_marker(self, marker: Any) -> bool:
        """Check if this type has a specific marker.

        Args:
            marker: The marker to check for.

        Returns:
            True if the marker is present, False otherwise.
        """
        return marker in self.markers

    def without_marker(self, marker: Any) -> NormalizedType:
        """Create a new NormalizedType with a specific marker removed.

        This does NOT re-normalize type_args. Use `renormalize_args_without_marker`
        if you need to strip the marker from type arguments as well.

        Args:
            marker: The marker to remove.

        Returns:
            A new NormalizedType with the marker removed from markers.
        """
        new_markers = tuple(m for m in self.markers if m is not marker)
        return dataclasses.replace(self, markers=new_markers)

    def renormalize_args_without_marker(self, marker: Any) -> NormalizedType:
        """Re-normalize type arguments with a specific marker excluded.

        This is useful for cases like UseAppendAction, where the inner type
        should not inherit the marker.

        Args:
            marker: The marker to exclude when re-normalizing type arguments.

        Returns:
            A new NormalizedType with re-normalized type_args.
        """
        if self._raw_type_args is None:
            return self

        # Re-normalize with the marker stripped from inheritance.
        # We set the context directly to override any outer context.
        filtered_markers = tuple(m for m in self.markers if m is not marker)
        token = _inherited_markers.set(filtered_markers)
        try:
            new_type_args = tuple(
                NormalizedType.normalize(arg) for arg in self._raw_type_args
            )
        finally:
            _inherited_markers.reset(token)

        return dataclasses.replace(self, type_args=new_type_args)

    @property
    def markers_as_set(self) -> set[Any]:
        """Get markers as a set for compatibility with existing code.

        Returns:
            A set containing all markers.
        """
        return set(self.markers)
