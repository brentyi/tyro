import copy
import dataclasses
import functools
from typing import Dict, List, Tuple, Type, TypeVar, Union

from typing_extensions import _GenericAlias, get_type_hints  # type: ignore


def is_dataclass(cls: Union[Type, _GenericAlias]) -> bool:
    """Same as `dataclasses.is_dataclass`, but also handles generic aliases."""
    return dataclasses.is_dataclass(cls) or (
        isinstance(cls, _GenericAlias) and dataclasses.is_dataclass(cls.__origin__)
    )


def resolve_generic_dataclasses(
    cls: Union[Type, _GenericAlias],
) -> Tuple[Type, Dict[TypeVar, Type]]:
    """If the input is a dataclass: no-op. If it's a generic alias: returns the root
    dataclass, and a mapping from typevars to concrete types."""

    if isinstance(cls, _GenericAlias):
        typevars = cls.__origin__.__parameters__
        typevar_values = cls.__args__
        assert len(typevars) == len(typevar_values)
        cls = cls.__origin__
        return cls, dict(zip(typevars, typevar_values))
    else:
        return cls, {}


@functools.lru_cache(maxsize=16)
def resolved_fields(cls: Union[Type, _GenericAlias]) -> List[dataclasses.Field]:
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
