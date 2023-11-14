"""Utilities for resolving types and forward references."""

import collections.abc
import copy
import dataclasses
import sys
import types
import warnings
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    FrozenSet,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from typing_extensions import Annotated, get_args, get_origin, get_type_hints

from . import _fields, _unsafe_cache
from ._typing import TypeForm

TypeOrCallable = TypeVar("TypeOrCallable", TypeForm[Any], Callable)


def unwrap_origin_strip_extras(typ: TypeOrCallable) -> TypeOrCallable:
    """Returns the origin, ignoring typing.Annotated, of typ if it exists. Otherwise,
    returns typ."""
    # TODO: Annotated[] handling should be revisited...
    typ, _ = unwrap_annotated(typ)
    origin = get_origin(typ)
    if origin is None:
        return typ
    else:
        return origin


def is_dataclass(cls: Union[TypeForm, Callable]) -> bool:
    """Same as `dataclasses.is_dataclass`, but also handles generic aliases."""
    return dataclasses.is_dataclass(unwrap_origin_strip_extras(cls))


def resolve_generic_types(
    cls: TypeOrCallable,
) -> Tuple[TypeOrCallable, Dict[TypeVar, TypeForm[Any]]]:
    """If the input is a class: no-op. If it's a generic alias: returns the origin
    class, and a mapping from typevars to concrete types."""

    origin_cls = get_origin(cls)

    type_from_typevar = {}
    if (
        # Apply some heuristics for generic types. Should revisit this.
        origin_cls is not None
        and hasattr(origin_cls, "__parameters__")
        and hasattr(origin_cls.__parameters__, "__len__")
    ):
        typevars = origin_cls.__parameters__
        typevar_values = get_args(cls)
        assert len(typevars) == len(typevar_values)
        cls = origin_cls
        type_from_typevar.update(dict(zip(typevars, typevar_values)))

    if hasattr(cls, "__orig_bases__"):
        bases = getattr(cls, "__orig_bases__")
        for base in bases:
            origin_base = unwrap_origin_strip_extras(base)
            if origin_base is base or not hasattr(origin_base, "__parameters__"):
                continue
            typevars = origin_base.__parameters__
            typevar_values = get_args(base)
            type_from_typevar.update(dict(zip(typevars, typevar_values)))

    return cls, type_from_typevar


@_unsafe_cache.unsafe_cache(maxsize=1024)
def resolved_fields(cls: TypeForm) -> List[dataclasses.Field]:
    """Similar to dataclasses.fields(), but includes dataclasses.InitVar types and
    resolves forward references."""

    assert dataclasses.is_dataclass(cls)
    fields = []
    annotations = get_type_hints(cls, include_extras=True)
    for field in getattr(cls, "__dataclass_fields__").values():
        # Avoid mutating original field.
        field = copy.copy(field)

        # Resolve forward references.
        field.type = annotations[field.name]

        # Skip ClassVars.
        if get_origin(field.type) is ClassVar:
            continue

        # Unwrap InitVar types.
        if isinstance(field.type, dataclasses.InitVar):
            field.type = field.type.type

        fields.append(field)

    return fields


def is_namedtuple(cls: TypeForm) -> bool:
    return (
        hasattr(cls, "_fields")
        # `_field_types` was removed in Python >=3.9.
        # and hasattr(cls, "_field_types")
        and hasattr(cls, "_field_defaults")
    )


def type_from_typevar_constraints(typ: TypeOrCallable) -> TypeOrCallable:
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


@_unsafe_cache.unsafe_cache(maxsize=1024)
def narrow_type(typ: TypeOrCallable, default_instance: Any) -> TypeOrCallable:
    """Type narrowing: if we annotate as Animal but specify a default instance of Cat,
    we should parse as Cat.

    This should generally only be applied to fields used as nested structures, not
    individual arguments/fields. (if a field is annotated as Union[int, str], and a
    string default is passed in, we don't want to narrow the type to always be
    strings!)"""
    try:
        potential_subclass = type(default_instance)

        if potential_subclass is type:
            # Don't narrow to `type`. This happens when the default instance is a class;
            # it doesn't really make sense to parse this case.
            return typ

        superclass = unwrap_annotated(typ)[0]

        # For Python 3.10.
        if get_origin(superclass) is Union:
            return typ

        if superclass is Any or issubclass(potential_subclass, superclass):  # type: ignore
            if get_origin(typ) is Annotated:
                return Annotated.__class_getitem__(  # type: ignore
                    (potential_subclass,) + get_args(typ)[1:]
                )
            typ = cast(TypeOrCallable, potential_subclass)
    except TypeError:
        # TODO: document where this TypeError can be raised, and reduce the amount of
        # code in it.
        pass

    return typ


def narrow_container_types(
    typ: TypeOrCallable, default_instance: Any
) -> TypeOrCallable:
    """TypeForm narrowing for containers. Infers types of container contents."""
    if typ is list and isinstance(default_instance, list):
        typ = List.__getitem__(Union.__getitem__(tuple(map(type, default_instance))))  # type: ignore
    elif typ is set and isinstance(default_instance, set):
        typ = Set.__getitem__(Union.__getitem__(tuple(map(type, default_instance))))  # type: ignore
    elif typ is tuple and isinstance(default_instance, tuple):
        typ = Tuple.__getitem__(tuple(map(type, default_instance)))  # type: ignore
    return typ


MetadataType = TypeVar("MetadataType")


def unwrap_annotated(
    typ: TypeOrCallable, search_type: Optional[TypeForm[MetadataType]] = None
) -> Tuple[TypeOrCallable, Tuple[MetadataType, ...]]:
    """Helper for parsing typing.Annotated types.

    Examples:
    - int, int => (int, ())
    - Annotated[int, 1], int => (int, (1,))
    - Annotated[int, "1"], int => (int, ())
    """
    targets = tuple(
        x
        for x in getattr(typ, "__tyro_markers__", tuple())
        if search_type is not None and isinstance(x, search_type)
    )
    assert isinstance(targets, tuple)
    if not hasattr(typ, "__metadata__"):
        return typ, targets

    args = get_args(typ)
    assert len(args) >= 2

    # Look through metadata for desired metadata type.
    targets = tuple(
        x
        for x in targets + args[1:]
        if search_type is not None and isinstance(x, search_type)
    )
    return args[0], targets


def apply_type_from_typevar(
    typ: TypeOrCallable, type_from_typevar: Dict[TypeVar, TypeForm[Any]]
) -> TypeOrCallable:
    if typ in type_from_typevar:
        return type_from_typevar[typ]  # type: ignore

    if len(get_args(typ)) > 0:
        args = get_args(typ)
        if get_origin(typ) is Annotated:
            args = args[:1]
        if get_origin(typ) is collections.abc.Callable:
            assert isinstance(args[0], list)
            args = tuple(args[0]) + args[1:]

        # Convert Python 3.9 and 3.10 types to their typing library equivalents, which
        # support `.copy_with()`.
        if sys.version_info[:2] >= (3, 9):
            shim_table = {
                # PEP 585. Requires Python 3.9.
                tuple: Tuple,
                list: List,
                dict: Dict,
                set: Set,
                frozenset: FrozenSet,
            }
            if hasattr(types, "UnionType"):  # type: ignore
                # PEP 604. Requires Python 3.10.
                shim_table[types.UnionType] = Union  # type: ignore

            for new, old in shim_table.items():
                if isinstance(typ, new) or get_origin(typ) is new:  # type: ignore
                    typ = old.__getitem__(args)  # type: ignore

        return typ.copy_with(tuple(apply_type_from_typevar(x, type_from_typevar) for x in args))  # type: ignore

    return typ


@_unsafe_cache.unsafe_cache(maxsize=1024)
def narrow_union_type(typ: TypeOrCallable, default_instance: Any) -> TypeOrCallable:
    """Narrow union types.

    This is a shim for failing more gracefully when we we're given one of two errors:
    (A) A Union type that doesn't match the default value.
    (B) An unsupported Union type, which mixes "nested" types (like dataclasses) with
      non-"nested" types (like strings).

    --
    For (A):

    We raise a warning, then take the type of the default value.
    Loosely motivated by: https://github.com/brentyi/tyro/issues/20

    --
    For (B):

    When do we want to narrow Union types?

      Unions over nested types: no.
         typ = NestedA | NestedB
         => NestedA | NestedB can be converted to two subcommands.

      Unions over nested and not nested types: no.
         typ = int | str
         => int | str can be instantiated as a union.

      Unions over mixed nested / not nested types: if the default is a nested
      type, strip out the non-nested ones. If the default is a non-nested
      type, strip out the nested ones.

         typ = NestedA | int, default_instance = NestedA()
         => NestedA

         typ = NestedA | int, default_instance = 5
         => int

         typ = NestedA | NestedB | int, default_instance = NestedA()
         => NestedA

    This is a hack to get around the fact that we don't currently support
    mixing nested types (eg `SomeDataclass`) and non-nested ones (eg `int` or
    `int | str`) in unions. This should be supported in the future, but will
    likely require a big code refactor."""
    if get_origin(typ) is not Union:
        return typ

    options = get_args(typ)
    options_unwrapped = [unwrap_origin_strip_extras(o) for o in options]

    # (A)
    try:
        if default_instance not in _fields.MISSING_SINGLETONS and not any(
            isinstance(default_instance, o) for o in options_unwrapped
        ):
            warnings.warn(
                f"{type(default_instance)} does not match any type in Union:"
                f" {options_unwrapped}"
            )
            return type(default_instance)
    except TypeError:
        pass

    # (B)
    is_nested = tuple(
        map(
            lambda option: _fields.is_nested_type(
                option,
                _fields.MISSING_NONPROP,
            ),
            options,
        )
    )
    if type(None) in options:
        none_index = options.index(type(None))
        is_nested_no_none = is_nested[:none_index] + is_nested[none_index + 1 :]
    else:
        is_nested_no_none = is_nested

    if all(is_nested_no_none) or not any(is_nested_no_none):
        # Either all types are nested or none of them are.
        return typ
    else:
        is_default_nested = _fields.is_nested_type(type(default_instance), default_instance)  # type: ignore
        out = Union.__getitem__(  # type: ignore
            tuple(
                option
                for option, nested in zip(get_args(typ), is_nested)
                if nested is is_default_nested
            )
        )
        return out  # type: ignore
