"""Utilities for resolving generic types and forward references."""

import copy
import dataclasses
from typing import Callable, Dict, List, Tuple, Type, TypeVar, Union

from typing_extensions import get_args, get_origin, get_type_hints

TypeOrCallable = TypeVar("TypeOrCallable", Type, Callable)


def unwrap_origin(tp: TypeOrCallable) -> TypeOrCallable:
    """Returns the origin of tp if it exists. Otherwise, returns tp."""
    origin = get_origin(tp)
    if origin is None:
        return tp
    else:
        return origin


def is_dataclass(cls: Union[Type, Callable]) -> bool:
    """Same as `dataclasses.is_dataclass`, but also handles generic aliases."""
    return dataclasses.is_dataclass(unwrap_origin(cls))


def resolve_generic_types(
    cls: TypeOrCallable,
) -> Tuple[TypeOrCallable, Dict[TypeVar, Type]]:
    """If the input is a class: no-op. If it's a generic alias: returns the origin
    class, and a mapping from typevars to concrete types."""

    origin_cls = get_origin(cls)
    if origin_cls is not None and hasattr(origin_cls, "__parameters__"):
        typevars = origin_cls.__parameters__
        typevar_values = get_args(cls)
        assert len(typevars) == len(typevar_values)
        return origin_cls, dict(zip(typevars, typevar_values))
    else:
        return cls, {}


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


def is_namedtuple(cls: Type) -> bool:
    return (
        hasattr(cls, "_fields")
        # Remove in Python >=3.9.
        # and hasattr(cls, "_field_types")
        and hasattr(cls, "_field_defaults")
    )
