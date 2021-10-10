import copy
import dataclasses
import functools
from typing import Dict, List, Tuple, Type, TypeVar, Union

from typing_extensions import _GenericAlias, get_type_hints  # type: ignore

TypeOrGeneric = Union[Type, _GenericAlias]


def is_dataclass(cls: TypeOrGeneric) -> bool:
    return dataclasses.is_dataclass(cls) or (
        isinstance(cls, _GenericAlias) and dataclasses.is_dataclass(cls.__origin__)
    )


def resolve_generic_dataclasses(cls: TypeOrGeneric) -> Tuple[Type, Dict[TypeVar, Type]]:
    if isinstance(cls, _GenericAlias):
        typevars = cls.__origin__.__parameters__
        typevar_values = cls.__args__
        assert len(typevars) == len(typevar_values)
        cls = cls.__origin__
        return cls, dict(zip(typevars, typevar_values))
    else:
        return cls, {}


@functools.lru_cache(maxsize=None)
def resolved_fields(cls: TypeOrGeneric) -> List[dataclasses.Field]:
    """Similar to dataclasses.fields, but resolves forward references."""

    assert dataclasses.is_dataclass(cls)
    fields = []
    annotations = get_type_hints(cls)
    for field in dataclasses.fields(cls):
        # Avoid mutating original field
        field = copy.copy(field)

        # Resolve forward references
        field.type = annotations[field.name]

        fields.append(field)

    return fields
