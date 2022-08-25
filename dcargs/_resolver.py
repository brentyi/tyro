"""Utilities for resolving types and forward references."""

import copy
import dataclasses
from typing import Any, Callable, Dict, List, Tuple, Type, TypeVar, Union, cast

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

    type_from_typevars = {}
    if origin_cls is not None and hasattr(origin_cls, "__parameters__"):
        typevars = origin_cls.__parameters__
        typevar_values = get_args(cls)
        assert len(typevars) == len(typevar_values)
        cls = origin_cls
        type_from_typevars.update(dict(zip(typevars, typevar_values)))

    if hasattr(cls, "__orig_bases__"):
        bases = getattr(cls, "__orig_bases__")
        for base in bases:
            origin_base = unwrap_origin(base)
            if origin_base is base or not hasattr(origin_base, "__parameters__"):
                continue
            typevars = origin_base.__parameters__
            typevar_values = get_args(base)
            type_from_typevars.update(dict(zip(typevars, typevar_values)))

    return cls, type_from_typevars


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
        # `_field_types` was removed in Python >=3.9.
        # and hasattr(cls, "_field_types")
        and hasattr(cls, "_field_defaults")
    )


def type_from_typevar_constraints(typ: Union[Type, TypeVar]) -> Union[Type, TypeVar]:
    """Try to concretize a type from a TypeVar's bounds or constraints. Identity if
    unsuccessful."""
    if isinstance(typ, TypeVar):
        if typ.__bound__ is not None:
            # Try to infer type from TypeVar bound.
            return typ.__bound__
        elif len(typ.__constraints__) > 0:
            # Try to infer type from TypeVar constraints.
            return Union.__getitem__(typ.__constraints__)  # type: ignore
    return typ


# Be a little bit permissive with types here, since we often blur the lines between
# Callable[..., T] and Type[T]... this could be cleaned up!
TypeT = TypeVar("TypeT", bound=Callable)


def narrow_type(typ: TypeT, default_instance: Any) -> TypeT:
    """Type narrowing: if we annotate as Animal but specify a default instance of Cat, we
    should parse as Cat."""
    try:
        potential_subclass = type(default_instance)
        superclass = typ
        if superclass is Any or issubclass(potential_subclass, superclass):  # type: ignore
            return cast(TypeT, potential_subclass)
    except TypeError:
        pass
    return typ
