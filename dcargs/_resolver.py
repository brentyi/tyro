import copy
import dataclasses
import functools
from typing import Dict, List, Optional, Tuple, Type, TypeVar, Union

from typing_extensions import get_type_hints


def unwrap_generic(cls: Type) -> Optional[Type]:
    """Returns the origin of a generic type; or None if not a generic."""
    # Note that isinstance(cls, GenericAlias) breaks in Python >= 3.9
    return cls.__origin__ if hasattr(cls, "__origin__") else None


def is_dataclass(cls: Type) -> bool:
    """Same as `dataclasses.is_dataclass`, but also handles generic aliases."""
    origin_cls = unwrap_generic(cls)
    return dataclasses.is_dataclass(cls if origin_cls is None else origin_cls)


def resolve_generic_dataclasses(
    cls: Type,
) -> Tuple[Type, Dict[TypeVar, Type]]:
    """If the input is a dataclass: no-op. If it's a generic alias: returns the root
    dataclass, and a mapping from typevars to concrete types."""

    origin_cls = unwrap_generic(cls)
    if origin_cls is not None:
        typevars = origin_cls.__parameters__
        typevar_values = cls.__args__
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
