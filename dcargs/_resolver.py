"""Utilities for resolving generic types and forward references."""

import copy
import dataclasses
import functools
from typing import Dict, List, Tuple, Type, TypeVar

from typing_extensions import get_args, get_origin, get_type_hints


def is_dataclass(cls: Type) -> bool:
    """Same as `dataclasses.is_dataclass`, but also handles generic aliases."""
    origin_cls = get_origin(cls)
    return dataclasses.is_dataclass(cls if origin_cls is None else origin_cls)


def resolve_generic_classes(
    cls: Type,
) -> Tuple[Type, Dict[TypeVar, Type]]:
    """If the input is a class: no-op. If it's a generic alias: returns the origin
    class, and a mapping from typevars to concrete types."""

    origin_cls = get_origin(cls)
    if origin_cls is not None:
        typevars = origin_cls.__parameters__
        typevar_values = get_args(cls)
        assert len(typevars) == len(typevar_values)
        return origin_cls, dict(zip(typevars, typevar_values))
    else:
        return cls, {}


@functools.lru_cache(maxsize=16)
def resolved_fields(cls: Type) -> List[dataclasses.Field]:
    """Similar to dataclasses.fields, but resolves forward references."""

    assert dataclasses.is_dataclass(cls)
    fields = []
    annotations = get_type_hints(cls)
    for field in dataclasses.fields(cls):
        # Avoid mutating original field.
        field = copy.copy(field)

        # Resolve forward references.
        field.type = annotations[field.name]

        fields.append(field)

    return fields
