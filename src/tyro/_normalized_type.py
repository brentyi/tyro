"""NormalizedType: A type with Annotated stripped and markers extracted.

This module contains the NormalizedType class which represents a type that has been
normalized by stripping one layer of `typing.Annotated` and extracting markers and
metadata. Type arguments are recursively normalized with inherited markers passed
explicitly.

Example::

    # User writes:
    x: Annotated[list[T], SomeMarker] = [1, 2, 3]

    # After normalization (T -> int resolved externally):
    NormalizedType(
        type=list[int],
        markers=(SomeMarker,),
        type_args=(NormalizedType(type=int, ...),),
        ...
    )
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable
from typing import Type as TypeForm

from typing_extensions import get_args, get_origin

from .conf import _markers


@dataclasses.dataclass(frozen=True)
class NormalizedType:
    """A normalized type with extracted metadata and markers.

    This class encapsulates a type that has been normalized by stripping one
    layer of `typing.Annotated` and extracting markers and metadata. The
    `type_args` are recursively normalized with inherited markers passed
    explicitly.

    Attributes:
        type: The type after stripping one layer of Annotated. May still
            contain nested Annotated types.
        type_origin: The result of `get_origin(type)`, or None for non-generic types.
        type_args: Pre-normalized type arguments with inherited markers.
            None if the type has no type arguments.
        markers: Tuple of tyro markers extracted from the type annotation,
            combined with inherited markers passed via from_type().
        metadata: Tuple of all non-marker metadata from the Annotated type.
    """

    type: TypeForm[Any] | Callable[..., Any]
    type_origin: Any | None
    type_args: tuple[NormalizedType, ...] | None
    markers: tuple[Any, ...]
    metadata: tuple[Any, ...]
    _raw_type_args: tuple[Any, ...] | None = dataclasses.field(
        default=None, repr=False, compare=False
    )

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

    @classmethod
    def from_type(
        cls,
        typ: Any,
        inherit_markers: tuple[Any, ...] = (),
    ) -> NormalizedType:
        """Normalize a type by stripping one layer of Annotated.

        This method:
        1. Strips one layer of `typing.Annotated` from the type
        2. Extracts markers and metadata from the annotation
        3. Combines extracted markers with inherited markers
        4. Recursively normalizes type arguments with the combined markers

        Args:
            typ: The type to normalize.
            inherit_markers: Markers to inherit from the parent context.

        Returns:
            A NormalizedType instance with the normalized type information.
        """
        from . import _resolver

        # Extract markers from the type annotation.
        unwrapped_typ, extra_markers = _resolver.unwrap_annotated(
            typ, search_type=_markers._Marker
        )

        # Get all metadata (not just markers).
        _, all_metadata = _resolver.unwrap_annotated(typ, search_type="all")

        # Combine inherited and extracted markers as tuple.
        markers = inherit_markers + tuple(extra_markers)

        # Extract non-marker metadata.
        metadata = tuple(m for m in all_metadata if not isinstance(m, _markers._Marker))

        # Get origin and raw type args.
        type_origin = get_origin(unwrapped_typ)
        raw_args = get_args(unwrapped_typ)

        # Recursively normalize type arguments with inherited markers.
        if len(raw_args) > 0:
            type_args = tuple(
                cls.from_type(
                    arg,
                    inherit_markers=markers,
                )
                for arg in raw_args
            )
        else:
            type_args = None

        return cls(
            type=unwrapped_typ,
            type_origin=type_origin,
            type_args=type_args,
            markers=markers,
            metadata=metadata,
            _raw_type_args=raw_args if len(raw_args) > 0 else None,
        )

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
        filtered_markers = tuple(m for m in self.markers if m != marker)
        new_type_args = tuple(
            NormalizedType.from_type(
                arg,
                inherit_markers=filtered_markers,
            )
            for arg in self._raw_type_args
        )

        return dataclasses.replace(self, type_args=new_type_args)
