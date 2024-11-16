"""Utilities for resolving types and forward references."""

from __future__ import annotations

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
    List,
    Sequence,
    Set,
    Tuple,
    Type,
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

from . import _unsafe_cache, conf
from ._singleton import MISSING_AND_MISSING_NONPROP
from ._typing import TypeForm

UnionType = getattr(types, "UnionType", Union)
"""Same as types.UnionType, but points to typing.Union for older versions of
Python. types.UnionType was added in Python 3.10, and is created when the `X |
Y` syntax is used for unions."""

TypeOrCallable = TypeVar("TypeOrCallable", TypeForm[Any], Callable)


@dataclasses.dataclass(frozen=True)
class TyroTypeAliasBreadCrumb:
    """A breadcrumb we can leave behind to track names of type aliases and
    `NewType` types. We can use type alias names to auto-populate
    subcommands."""

    name: str


def unwrap_origin_strip_extras(typ: TypeOrCallable) -> TypeOrCallable:
    """Returns the origin, ignoring typing.Annotated, of typ if it exists. Otherwise,
    returns typ."""
    typ = unwrap_annotated(typ)
    origin = get_origin(typ)

    if origin is not None:
        typ = origin

    return typ


def is_dataclass(cls: Union[TypeForm, Callable]) -> bool:
    """Same as `dataclasses.is_dataclass`, but also handles generic aliases."""
    return dataclasses.is_dataclass(unwrap_origin_strip_extras(cls))  # type: ignore


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
        else:
            return Any
    return typ


TypeOrCallableOrNone = TypeVar("TypeOrCallableOrNone", Callable, TypeForm[Any], None)


def resolve_newtype_and_aliases(
    typ: TypeOrCallableOrNone,
) -> TypeOrCallableOrNone:
    # Handle type aliases, eg via the `type` statement in Python 3.12.
    if isinstance(typ, TypeAliasType):
        return Annotated[
            (
                cast(Any, resolve_newtype_and_aliases(typ.__value__)),
                TyroTypeAliasBreadCrumb(typ.__name__),
            )
        ]

    # We'll unwrap NewType annotations here; this is needed before issubclass
    # checks!
    #
    # `isinstance(x, NewType)` doesn't work because NewType isn't a class until
    # Python 3.10, so we instead do a duck typing-style check.
    return_name = None
    while hasattr(typ, "__name__") and hasattr(typ, "__supertype__"):
        if return_name is None:
            return_name = getattr(typ, "__name__")
        typ = resolve_newtype_and_aliases(getattr(typ, "__supertype__"))

    if return_name is not None:
        typ = Annotated[(typ, TyroTypeAliasBreadCrumb(return_name))]  # type: ignore

    return cast(TypeOrCallableOrNone, typ)


@_unsafe_cache.unsafe_cache(maxsize=1024)
def narrow_subtypes(
    typ: TypeOrCallable,
    default_instance: Any,
) -> TypeOrCallable:
    """Type narrowing: if we annotate as Animal but specify a default instance of Cat,
    we should parse as Cat.

    This should generally only be applied to fields used as nested structures, not
    individual arguments/fields. (if a field is annotated as Union[int, str], and a
    string default is passed in, we don't want to narrow the type to always be
    strings!)"""

    typ = resolve_newtype_and_aliases(typ)

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
                return Annotated[(potential_subclass,) + get_args(typ)[1:]]  # type: ignore
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
                    conf._confstruct._ArgConfig,
                    conf._confstruct._SubcommandConfig,
                ),
            )
            and anno.constructor_factory is not None
        ):
            return Annotated[(anno.constructor_factory(),) + annotations]  # type: ignore
    return typ


def narrow_collection_types(
    typ: TypeOrCallable, default_instance: Any
) -> TypeOrCallable:
    """TypeForm narrowing for containers. Infers types of container contents."""
    args = get_args(typ)
    origin = get_origin(typ)
    if args == (Any,) or (origin is tuple and args == (Any, Ellipsis)):
        typ = origin  # type: ignore

    if typ in (list, Sequence, collections.abc.Sequence) and isinstance(
        default_instance, list
    ):
        if len(default_instance) == 0:
            return typ
        typ = List.__getitem__(Union.__getitem__(tuple(map(type, default_instance))))  # type: ignore
    elif typ in (set, Sequence, collections.abc.Sequence) and isinstance(
        default_instance, set
    ):
        if len(default_instance) == 0:
            return typ
        typ = Set.__getitem__(Union.__getitem__(tuple(map(type, default_instance))))  # type: ignore
    elif typ in (tuple, Sequence, collections.abc.Sequence) and isinstance(
        default_instance, tuple
    ):
        if len(default_instance) == 0:
            return typ
        typ = Tuple.__getitem__(tuple(map(type, default_instance)))  # type: ignore
    return cast(TypeOrCallable, typ)


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

    # Unwrap aliases defined using Python 3.12's `type` syntax.
    typ = resolve_newtype_and_aliases(typ)

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


class TypeParamResolver:
    param_assignments: List[Dict[TypeVar, TypeForm[Any]]] = []

    @classmethod
    def get_assignment_context(cls, typ: TypeOrCallable) -> TypeParamAssignmentContext:
        """Context manager for resolving type parameters."""
        typ, type_from_typevar = resolve_generic_types(typ)
        return TypeParamAssignmentContext(typ, type_from_typevar)

    @staticmethod
    def concretize_type_params(
        typ: TypeOrCallable, seen: set[Any] | None = None
    ) -> TypeOrCallable:
        """Apply type parameter assignments based on the current context."""

        if seen is None:
            seen = set()
        elif seen is not None and typ in seen:
            # Found a cycle. We don't (currently) support recursive types.
            return typ
        else:
            seen.add(typ)

        typ = resolve_newtype_and_aliases(typ)
        type_from_typevar = {}
        GenericAlias = getattr(types, "GenericAlias", None)
        while (
            GenericAlias is not None
            and isinstance(typ, GenericAlias)
            and len(getattr(typ, "__type_params__", ())) > 0
        ):
            for k, v in zip(typ.__type_params__, get_args(typ)):  # type: ignore
                type_from_typevar[k] = TypeParamResolver.concretize_type_params(
                    v, seen=seen
                )
            typ = typ.__value__  # type: ignore

        if len(type_from_typevar) == 0:
            return TypeParamResolver._concretize_type_params(typ, seen=seen)
        else:
            with TypeParamAssignmentContext(typ, type_from_typevar):
                return TypeParamResolver._concretize_type_params(typ, seen=seen)

    @staticmethod
    def _concretize_type_params(typ: TypeOrCallable, seen: set[Any]) -> TypeOrCallable:
        for type_from_typevar in reversed(TypeParamResolver.param_assignments):
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

            new_args_list = []
            for x in args:
                for type_from_typevar in reversed(TypeParamResolver.param_assignments):
                    if x in type_from_typevar:
                        x = type_from_typevar[x]
                        break
                new_args_list.append(x)

            new_args = tuple(
                TypeParamResolver.concretize_type_params(x, seen=seen)
                for x in new_args_list
            )

            # Standard generic aliases have a `copy_with()`!
            if origin is UnionType:
                return Union.__getitem__(new_args)  # type: ignore
            elif hasattr(typ, "copy_with"):
                # typing.List, typing.Dict, etc.
                return typ.copy_with(new_args)  # type: ignore
            else:
                # list[], dict[], etc.
                assert origin is not None
                return origin[new_args]

        return typ  # type: ignore


class TypeParamAssignmentContext:
    def __init__(
        self,
        origin_type: TypeOrCallable,
        type_from_typevar: Dict[TypeVar, TypeForm[Any]],
    ):
        # `Any` is needed for mypy...
        self.origin_type: Any = origin_type
        self.type_from_typevar = type_from_typevar

    def __enter__(self):
        TypeParamResolver.param_assignments.append(self.type_from_typevar)

    def __exit__(self, exc_type, exc_value, traceback):
        TypeParamResolver.param_assignments.pop()


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

    try:
        if default_instance not in MISSING_AND_MISSING_NONPROP and not any(
            isinstance_with_fuzzy_numeric_tower(default_instance, o) is not False
            for o in options_unwrapped
        ):
            warnings.warn(
                f"{type(default_instance)} does not match any type in Union:"
                f" {options_unwrapped}"
            )
            return Union.__getitem__(options + (type(default_instance),))  # type: ignore
    except TypeError:
        pass

    return typ


def isinstance_with_fuzzy_numeric_tower(
    obj: Any, classinfo: Type
) -> Union[bool, Literal["~"]]:
    """
    Enhanced version of isinstance() that returns:
    - True: if object is exactly of the specified type
    - "~": if object follows numeric tower rules but isn't exact type
    - False: if object is not of the specified type or numeric tower rules don't apply

    Examples:
    >>> enhanced_isinstance(3, int)       # Returns True
    >>> enhanced_isinstance(3, float)     # Returns "~"
    >>> enhanced_isinstance(True, int)    # Returns "~"
    >>> enhanced_isinstance(3, bool)      # Returns False
    >>> enhanced_isinstance(True, bool)   # Returns True
    """
    # Handle exact match first
    if isinstance(obj, classinfo):
        return True

    # Handle numeric tower cases
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


NoneType = type(None)


def resolve_generic_types(
    typ: TypeOrCallable,
) -> Tuple[TypeOrCallable, Dict[TypeVar, TypeForm[Any]]]:
    """If the input is a class: no-op. If it's a generic alias: returns the origin
    class, and a mapping from typevars to concrete types."""

    annotations: Tuple[Any, ...] = ()
    if get_origin(typ) is Annotated:
        # ^We need this `if` statement for an obscure edge case: when `cls` is a
        # function with `__tyro_markers__` set, we don't want/need to return
        # Annotated[func, markers].
        typ, annotations = unwrap_annotated(typ, "all")

    # Apply shims to convert from types.UnionType to typing.Union, list to
    # typing.List, etc.
    typ = resolve_newtype_and_aliases(typ)

    # We'll ignore NewType when getting the origin + args for generics.
    origin_cls = get_origin(typ)
    type_from_typevar: Dict[TypeVar, TypeForm[Any]] = {}

    # Support typing.Self.
    # We'll do this by pretending that `Self` is a TypeVar...
    if hasattr(typ, "__self__"):
        self_type = getattr(typ, "__self__")
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
        typevar_values = get_args(resolve_newtype_and_aliases(typ))
        assert len(typevars) == len(typevar_values)
        typ = origin_cls
        type_from_typevar.update(dict(zip(typevars, typevar_values)))
    elif (
        # Apply some heuristics for generic types. Should revisit this.
        hasattr(typ, "__parameters__") and hasattr(typ.__parameters__, "__len__")  # type: ignore
    ):
        typevars = typ.__parameters__  # type: ignore
        typevar_values = tuple(type_from_typevar_constraints(x) for x in typevars)
        assert len(typevars) == len(typevar_values)
        type_from_typevar.update(dict(zip(typevars, typevar_values)))

    if hasattr(typ, "__orig_bases__"):
        bases = getattr(typ, "__orig_bases__")
        for base in bases:
            origin_base = unwrap_origin_strip_extras(base)
            if origin_base is base or not hasattr(origin_base, "__parameters__"):
                continue
            typevars = origin_base.__parameters__
            typevar_values = get_args(base)
            type_from_typevar.update(dict(zip(typevars, typevar_values)))

    if len(annotations) == 0:
        return typ, type_from_typevar
    else:
        return (
            Annotated[(typ, *annotations)],  # type: ignore
            type_from_typevar,
        )


def get_type_hints_with_backported_syntax(
    obj: Callable[..., Any], include_extras: bool = False
) -> Dict[str, Any]:
    """Same as `typing.get_type_hints()`, but supports new union syntax (X | Y)
    and generics (list[str]) in older versions of Python."""
    try:
        out = get_type_hints(obj, include_extras=include_extras)

        # Workaround for:
        # - https://github.com/brentyi/tyro/issues/156
        # - https://github.com/python/cpython/issues/90353
        #
        # Which impacts Python 3.10 and earlier.
        #
        # It may be possible to remove this if this issue is resolved:
        # - https://github.com/python/typing_extensions/issues/310
        if sys.version_info < (3, 11):
            # If we see Optional[Annotated[T, ...]], we're going to flip to Annotated[Optional[T]]...
            #
            # It's unlikely but possible for this to have unintended side effects.
            for k, v in out.items():
                origin = get_origin(v)
                args = get_args(v)
                if (
                    origin is Union
                    and len(args) == 2
                    and (args[0] is NoneType or args[1] is NoneType)
                ):
                    non_none = args[1] if args[0] is NoneType else args[0]
                    if get_origin(non_none) is Annotated:
                        annotated_args = get_args(non_none)
                        out[k] = Annotated[  # type: ignore
                            (
                                Union.__getitem__((annotated_args[0], None)),  # type: ignore
                                *annotated_args[1:],
                            )
                        ]
        return out

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
