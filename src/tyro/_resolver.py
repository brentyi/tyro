"""Utilities for resolving types and forward references."""

import collections.abc
import copy
import dataclasses
import inspect
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
    overload,
)

from typing_extensions import (
    Annotated,
    Final,
    ForwardRef,
    Literal,
    Self,
    TypeAliasType,
    get_args,
    get_origin,
    get_type_hints,
)

from . import _fields, _unsafe_cache, conf
from ._typing import TypeForm

TypeOrCallable = TypeVar("TypeOrCallable", TypeForm[Any], Callable)


def unwrap_origin_strip_extras(typ: TypeOrCallable) -> TypeOrCallable:
    """Returns the origin, ignoring typing.Annotated, of typ if it exists. Otherwise,
    returns typ."""
    # TODO: Annotated[] handling should be revisited...
    typ = unwrap_annotated(typ)
    origin = get_origin(typ)

    if origin is not None:
        typ = origin

    return typ


def is_dataclass(cls: Union[TypeForm, Callable]) -> bool:
    """Same as `dataclasses.is_dataclass`, but also handles generic aliases."""
    return dataclasses.is_dataclass(unwrap_origin_strip_extras(cls))  # type: ignore


def resolve_generic_types(
    cls: TypeOrCallable,
) -> Tuple[TypeOrCallable, Dict[TypeVar, TypeForm[Any]]]:
    """If the input is a class: no-op. If it's a generic alias: returns the origin
    class, and a mapping from typevars to concrete types."""

    annotations: Tuple[Any, ...] = ()
    if get_origin(cls) is Annotated:
        # ^We need this `if` statement for an obscure edge case: when `cls` is a
        # function with `__tyro_markers__` set, we don't want/need to return
        # Annotated[func, markers].
        cls, annotations = unwrap_annotated(cls, "all")

    # We'll ignore NewType when getting the origin + args for generics.
    origin_cls = get_origin(unwrap_newtype_and_aliases(cls)[0])
    type_from_typevar: Dict[TypeVar, TypeForm[Any]] = {}

    # Support typing.Self.
    # We'll do this by pretending that `Self` is a TypeVar...
    if hasattr(cls, "__self__"):
        self_type = getattr(cls, "__self__")
        if inspect.isclass(self_type):
            type_from_typevar[cast(TypeVar, Self)] = self_type  # type: ignore
        else:
            type_from_typevar[cast(TypeVar, Self)] = self_type.__class__  # type: ignore

    if (
        # Apply some heuristics for generic types. Should revisit this.
        origin_cls is not None
        and hasattr(origin_cls, "__parameters__")
        and hasattr(origin_cls.__parameters__, "__len__")
    ):
        typevars = origin_cls.__parameters__
        typevar_values = get_args(unwrap_newtype_and_aliases(cls)[0])
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

    if len(annotations) == 0:
        return cls, type_from_typevar
    else:
        return (
            Annotated.__class_getitem__((cls, *annotations)),  # type: ignore
            type_from_typevar,
        )


@_unsafe_cache.unsafe_cache(maxsize=1024)
def resolved_fields(cls: TypeForm) -> List[dataclasses.Field]:
    """Similar to dataclasses.fields(), but includes dataclasses.InitVar types and
    resolves forward references."""

    assert dataclasses.is_dataclass(cls)
    fields = []
    annotations = get_type_hints_with_backported_syntax(
        cast(Callable, cls), include_extras=True
    )
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


TypeOrCallableOrNone = TypeVar("TypeOrCallableOrNone", Callable, TypeForm[Any], None)


def unwrap_newtype_and_aliases(
    typ: TypeOrCallableOrNone,
) -> Tuple[TypeOrCallableOrNone, Optional[str]]:
    # Handle type aliases, eg via the `type` statement in Python 3.12.
    if isinstance(typ, TypeAliasType):
        return unwrap_newtype_and_aliases(typ.__value__)  # type: ignore

    # We'll unwrap NewType annotations here; this is needed before issubclass
    # checks!
    #
    # `isinstance(x, NewType)` doesn't work because NewType isn't a class until
    # Python 3.10, so we instead do a duck typing-style check.
    return_name = None
    while hasattr(typ, "__name__") and hasattr(typ, "__supertype__"):
        if return_name is None:
            return_name = getattr(typ, "__name__")
        typ = getattr(typ, "__supertype__")

    return typ, return_name


@_unsafe_cache.unsafe_cache(maxsize=1024)
def unwrap_newtype_and_narrow_subtypes(
    typ: TypeOrCallable,
    default_instance: Any,
) -> TypeOrCallable:
    """Type narrowing: if we annotate as Animal but specify a default instance of Cat,
    we should parse as Cat.

    This should generally only be applied to fields used as nested structures, not
    individual arguments/fields. (if a field is annotated as Union[int, str], and a
    string default is passed in, we don't want to narrow the type to always be
    strings!)"""

    typ, unused_name = unwrap_newtype_and_aliases(typ)
    del unused_name

    try:
        potential_subclass = type(default_instance)

        if potential_subclass is type:
            # Don't narrow to `type`. This happens when the default instance is a class;
            # it doesn't really make sense to parse this case.
            return typ

        superclass = unwrap_annotated(typ)

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


def swap_type_using_confstruct(typ: TypeOrCallable) -> TypeOrCallable:
    """Swap types using the `constructor_factory` attribute from
    `tyro.conf.arg` and `tyro.conf.subcommand`. Runtime annotations are
    kept, but the type is swapped."""
    # Need to swap types.
    _, annotations = unwrap_annotated(typ, search_type="all")
    for anno in reversed(annotations):
        if (
            isinstance(
                anno,
                (
                    conf._confstruct._ArgConfiguration,
                    conf._confstruct._SubcommandConfiguration,
                ),
            )
            and anno.constructor_factory is not None
        ):
            return Annotated.__class_getitem__(  # type: ignore
                (anno.constructor_factory(),) + annotations
            )
    return typ


def narrow_collection_types(
    typ: TypeOrCallable, default_instance: Any
) -> TypeOrCallable:
    """TypeForm narrowing for containers. Infers types of container contents."""
    if typ is list and isinstance(default_instance, list):
        if len(default_instance) == 0:
            return typ
        typ = List.__getitem__(Union.__getitem__(tuple(map(type, default_instance))))  # type: ignore
    elif typ is set and isinstance(default_instance, set):
        if len(default_instance) == 0:
            return typ
        typ = Set.__getitem__(Union.__getitem__(tuple(map(type, default_instance))))  # type: ignore
    elif typ is tuple and isinstance(default_instance, tuple):
        if len(default_instance) == 0:
            return typ
        typ = Tuple.__getitem__(tuple(map(type, default_instance)))  # type: ignore
    return typ


# `Final` and `ReadOnly` types are ignored in tyro.
try:
    # Can only import ReadOnly in typing_extensions>=4.9.0, which isn't
    # supported by Python 3.7.
    from typing_extensions import ReadOnly

    STRIP_WRAPPER_TYPES = {Final, ReadOnly}
except ImportError:
    STRIP_WRAPPER_TYPES = {Final}

MetadataType = TypeVar("MetadataType")


@overload
def unwrap_annotated(
    typ: TypeOrCallable,
    search_type: TypeForm[MetadataType],
) -> Tuple[TypeOrCallable, Tuple[MetadataType, ...]]: ...


@overload
def unwrap_annotated(
    typ: TypeOrCallable,
    search_type: Literal["all"],
) -> Tuple[TypeOrCallable, Tuple[Any, ...]]: ...


@overload
def unwrap_annotated(
    typ: TypeOrCallable,
    search_type: None = None,
) -> TypeOrCallable: ...


def unwrap_annotated(
    typ: TypeOrCallable,
    search_type: Union[TypeForm[MetadataType], Literal["all"], object, None] = None,
) -> Union[Tuple[TypeOrCallable, Tuple[MetadataType, ...]], TypeOrCallable]:
    """Helper for parsing typing.Annotated types.

    Examples:
    - int, int => (int, ())
    - Annotated[int, 1], int => (int, (1,))
    - Annotated[int, "1"], int => (int, ())
    """

    # `Final` and `ReadOnly` types are ignored in tyro.
    while get_origin(typ) in STRIP_WRAPPER_TYPES:
        typ = get_args(typ)[0]

    # Don't search for any annotations.
    if search_type is None:
        if not hasattr(typ, "__metadata__"):
            return typ
        else:
            return get_args(typ)[0]

    # Check for __tyro_markers__ from @configure.
    if hasattr(typ, "__tyro_markers__"):
        if search_type == "all":
            targets = getattr(typ, "__tyro_markers__")
        else:
            targets = tuple(
                x
                for x in getattr(typ, "__tyro_markers__")
                if isinstance(x, search_type)  # type: ignore
            )
    else:
        targets = ()

    assert isinstance(targets, tuple)
    if not hasattr(typ, "__metadata__"):
        return typ, targets  # type: ignore

    args = get_args(typ)
    assert len(args) >= 2

    # Look through metadata for desired metadata type.
    targets += tuple(
        x
        for x in targets + args[1:]
        if search_type == "all" or isinstance(x, search_type)  # type: ignore
    )

    # Check for __tyro_markers__ in unwrapped type.
    if hasattr(args[0], "__tyro_markers__"):
        targets += tuple(
            x
            for x in getattr(args[0], "__tyro_markers__")
            if search_type == "all" or isinstance(x, search_type)  # type: ignore
        )
    return args[0], targets  # type: ignore


def apply_type_from_typevar(
    typ: TypeOrCallable, type_from_typevar: Dict[TypeVar, TypeForm[Any]]
) -> TypeOrCallable:
    if typ in type_from_typevar:
        return type_from_typevar[typ]  # type: ignore

    origin = get_origin(typ)
    args = get_args(typ)
    if len(args) > 0:
        if origin is Annotated:
            args = args[:1]
        if origin is collections.abc.Callable:
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
                if isinstance(typ, new) or origin is new:  # type: ignore
                    typ = old.__getitem__(args)  # type: ignore

        return typ.copy_with(  # type: ignore
            tuple(apply_type_from_typevar(x, type_from_typevar) for x in args)
        )

    return typ


@_unsafe_cache.unsafe_cache(maxsize=1024)
def narrow_union_type(typ: TypeOrCallable, default_instance: Any) -> TypeOrCallable:
    """Narrow union types.

    This is a shim for failing more gracefully when we we're given a Union type that
    doesn't match the default value.

    In this case, we raise a warning, then add the type of the default value to the
    union. Loosely motivated by: https://github.com/brentyi/tyro/issues/20
    """
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
            return Union.__getitem__(options + (type(default_instance),))  # type: ignore
    except TypeError:
        pass

    return typ


def get_type_hints_with_backported_syntax(
    obj: Callable[..., Any], include_extras: bool = False
) -> Dict[str, Any]:
    """Same as `typing.get_type_hints()`, but supports new union syntax (X | Y)
    and generics (list[str]) in older versions of Python."""
    try:
        return get_type_hints(obj, include_extras=include_extras)
    except TypeError as e:  # pragma: no cover
        # Resolve new type syntax using eval_type_backport.
        if hasattr(obj, "__annotations__"):
            try:
                from eval_type_backport import eval_type_backport

                # Get global namespace for functions.
                globalns = getattr(obj, "__globals__", None)

                # Get global namespace for classes.
                if globalns is None and hasattr(globalns, "__init__"):
                    globalns = getattr(getattr(obj, "__init__"), "__globals__", None)

                out = {
                    k: eval_type_backport(ForwardRef(v), globalns=globalns, localns={})
                    for k, v in getattr(obj, "__annotations__").items()
                }
                return out
            except ImportError:
                pass
        raise e
