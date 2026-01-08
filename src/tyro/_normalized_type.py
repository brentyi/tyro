"""NormalizedType: type with Annotated stripped and markers extracted."""

from __future__ import annotations

import dataclasses
from typing import Any, Callable
from typing import Type as TypeForm

from typing_extensions import get_args, get_origin

from .conf import _markers


@dataclasses.dataclass(frozen=True)
class NormalizedType:
    """A normalized type with extracted metadata and markers.

    The type_args are recursively normalized with inherited markers.
    """

    type: TypeForm[Any] | Callable[..., Any]
    """The type after stripping one layer of Annotated."""
    type_origin: Any | None
    """Result of get_origin(type), or None for non-generic types."""
    type_args: tuple[NormalizedType, ...] | None
    """Pre-normalized type arguments, or None if no type arguments."""
    markers: tuple[Any, ...]
    """Tyro markers from the annotation, combined with inherited markers."""
    metadata: tuple[Any, ...]
    """Non-marker metadata from the Annotated type."""
    _raw_type_args: tuple[Any, ...] | None = dataclasses.field(
        default=None, repr=False, compare=False
    )

    @property
    def raw_type_args(self) -> tuple[Any, ...]:
        """Get raw (un-normalized) type arguments for re-normalization."""
        return self._raw_type_args if self._raw_type_args is not None else ()

    @classmethod
    def from_type(
        cls, typ: Any, inherit_markers: tuple[Any, ...] = ()
    ) -> NormalizedType:
        """Normalize a type by stripping Annotated and extracting markers."""
        from . import _resolver

        unwrapped_typ, extra_markers = _resolver.unwrap_annotated(
            typ, search_type=_markers._Marker
        )
        _, all_metadata = _resolver.unwrap_annotated(typ, search_type="all")
        markers = inherit_markers + tuple(extra_markers)
        metadata = tuple(m for m in all_metadata if not isinstance(m, _markers._Marker))
        type_origin = get_origin(unwrapped_typ)
        raw_args = get_args(unwrapped_typ)

        if len(raw_args) > 0:
            type_args = tuple(
                cls.from_type(arg, inherit_markers=markers) for arg in raw_args
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
        """Re-normalize type arguments with a specific marker excluded."""
        if self._raw_type_args is None:
            return self
        filtered_markers = tuple(m for m in self.markers if m != marker)
        new_type_args = tuple(
            NormalizedType.from_type(arg, inherit_markers=filtered_markers)
            for arg in self._raw_type_args
        )
        return dataclasses.replace(self, type_args=new_type_args)
