"""Utility functions for type inspection."""

from __future__ import annotations

import copy
import dataclasses
from typing import Any, Callable, List, Literal, Type, Union, cast

from typing_extensions import Annotated, get_args, get_origin

from .._typing_compat import is_typing_classvar
from ._typevar import get_type_hints_resolve_type_params
from ._unwrap import unwrap_origin_strip_extras


def is_dataclass(cls: Any) -> bool:
    """Same as `dataclasses.is_dataclass`, but also handles generic aliases."""
    return dataclasses.is_dataclass(unwrap_origin_strip_extras(cls))  # type: ignore


def resolved_fields(cls: Type) -> List[dataclasses.Field]:
    """Similar to dataclasses.fields(), but includes dataclasses.InitVar types and
    resolves forward references."""

    assert dataclasses.is_dataclass(cls)
    fields = []
    annotations = get_type_hints_resolve_type_params(
        cast(Callable, cls), include_extras=True
    )
    for field in getattr(cls, "__dataclass_fields__").values():
        # Avoid mutating original field.
        field = copy.copy(field)

        # Resolve forward references.
        field.type = annotations[field.name]

        # Skip ClassVars.
        if is_typing_classvar(get_origin(field.type)):
            continue

        # Unwrap InitVar types.
        if isinstance(field.type, dataclasses.InitVar):
            field.type = field.type.type

        fields.append(field)

    return fields


def is_namedtuple(cls: Any) -> bool:
    """Check if the type is a namedtuple."""
    return (
        isinstance(cls, type)
        and issubclass(cls, tuple)
        and hasattr(cls, "_fields")
        and hasattr(cls, "_asdict")
    )


def is_instance(typ: Any, value: Any) -> bool:
    """Typeguard-based alternative for `isinstance()`."""

    # Fast path: for plain types, use built-in isinstance.
    if type(typ) is type:
        return isinstance(value, typ)

    # Fast path: Handle Union types without importing typeguard.
    # This is common for subcommands: Union[Annotated[Config, ...], Annotated[Config, ...], ...]
    origin = get_origin(typ)
    if origin is Union:
        args = get_args(typ)
        # Recursively check each union member.
        return any(is_instance(arg, value) for arg in args)

    # Fast path: Handle Annotated types by unwrapping to the base type.
    if origin is Annotated:
        args = get_args(typ)
        if args:
            return is_instance(args[0], value)

    # Fast path: Handle Literal types.
    if origin is Literal:
        args = get_args(typ)
        return value in args

    # Slow path: For complex types, fall back to typeguard.
    # Import is lazy to avoid overhead when not needed.
    import typeguard

    try:
        typeguard.check_type(value, typ)
        return True
    except (typeguard.TypeCheckError, TypeError):
        return False


def isinstance_with_fuzzy_numeric_tower(
    obj: Any, classinfo: Type
) -> Union[bool, Literal["~"]]:
    """
    Enhanced version of isinstance() that returns:
    - True: if object is exactly of the specified type
    - "~": if object follows numeric tower rules but isn't exact type
    - False: if object is not of the specified type or numeric tower rules don't apply

    Examples:
    >>> isinstance_with_fuzzy_numeric_tower(3, int)       # Returns True
    >>> isinstance_with_fuzzy_numeric_tower(3, float)     # Returns "~"
    >>> isinstance_with_fuzzy_numeric_tower(True, int)    # Returns "~"
    >>> isinstance_with_fuzzy_numeric_tower(3, bool)      # Returns False
    >>> isinstance_with_fuzzy_numeric_tower(True, bool)   # Returns True
    """
    # Handle exact match first.
    if isinstance(obj, classinfo):
        return True

    # Handle numeric tower cases.
    if isinstance(obj, bool):
        if classinfo in (int, float, complex):
            return "~"
    elif isinstance(obj, int) and not isinstance(obj, bool):  # explicit bool check
        if classinfo in (float, complex):
            return "~"
    elif isinstance(obj, float):
        if classinfo is complex:
            return "~"

    return False
