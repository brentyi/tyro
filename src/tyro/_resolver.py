"""Utilities for resolving types and forward references."""

from __future__ import annotations

import collections.abc
import copy
import dataclasses
import inspect
import types
import typing
import warnings
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    List,
    Literal,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

import typeguard
from typing_extensions import (
    Annotated,
    Final,
    ForwardRef,
    ReadOnly,
    Self,
    TypeAliasType,
    get_args,
    get_origin,
    get_original_bases,
    get_type_hints,
)

from . import _unsafe_cache, conf
from ._singleton import MISSING_AND_MISSING_NONPROP
from ._typing import TypeForm

# typing_extensions.TypeAliasType and typing.TypeAliasType are not the same
# object in typing_extensions 4.13.0! This can break an isinstance() check we
# use below.
TypeAliasTypeAlternate = getattr(typing, "TypeAliasType", TypeAliasType)

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


# @_unsafe_cache.unsafe_cache(maxsize=1024)
def resolved_fields(cls: TypeForm) -> List[dataclasses.Field]:
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
        if get_origin(field.type) is ClassVar:
            continue

        # Unwrap InitVar types.
        if isinstance(field.type, dataclasses.InitVar):
            field.type = field.type.type

        fields.append(field)

    return fields


def is_namedtuple(cls: TypeForm) -> bool:
    return (
        isinstance(cls, type)
        and issubclass(cls, tuple)
        and hasattr(cls, "_fields")
        and hasattr(cls, "_asdict")
    )


TypeOrCallableOrNone = TypeVar("TypeOrCallableOrNone", Callable, TypeForm[Any], None)


def resolve_newtype_and_aliases(
    typ: TypeOrCallableOrNone,
) -> TypeOrCallableOrNone:
    # Handle type aliases, eg via the `type` statement in Python 3.12.
    if isinstance(typ, (TypeAliasType, TypeAliasTypeAlternate)):
        typ_cast = cast(TypeAliasType, typ)
        return Annotated[  # type: ignore
            (
                cast(Any, resolve_newtype_and_aliases(typ_cast.__value__)),
                TyroTypeAliasBreadCrumb(typ_cast.__name__),
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

    if default_instance in MISSING_AND_MISSING_NONPROP:
        return typ

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

    # Can't narrow if we don't have a default value!
    if default_instance in MISSING_AND_MISSING_NONPROP:
        return typ

    # We'll recursively narrow contained types too!
    def _get_type(val: Any) -> TypeForm:
        return narrow_collection_types(type(val), val)

    args = get_args(typ)
    origin = get_origin(typ)

    # We should attempt to narrow if we see `list[Any]`, `tuple[Any]`,
    # `tuple[Any, ...]`, etc.
    if args == (Any,) or (origin is tuple and args == (Any, Ellipsis)):
        typ = origin  # type: ignore

    if typ in (list, Sequence, collections.abc.Sequence) and isinstance(
        default_instance, list
    ):
        if len(default_instance) == 0:
            return typ
        typ = List[Union[tuple(map(_get_type, default_instance))]]  # type: ignore
    elif typ in (set, Sequence, collections.abc.Sequence) and isinstance(
        default_instance, set
    ):
        if len(default_instance) == 0:
            return typ
        typ = Set[Union[tuple(map(_get_type, default_instance))]]  # type: ignore
    elif typ in (tuple, Sequence, collections.abc.Sequence) and isinstance(
        default_instance, tuple
    ):
        if len(default_instance) == 0:
            return typ
        default_types = tuple(map(_get_type, default_instance))
        if len(set(default_types)) == 1:
            typ = Tuple[default_types[0], Ellipsis]  # type: ignore
        else:
            typ = Tuple[default_types]  # type: ignore
    elif (
        origin is tuple
        and isinstance(default_instance, tuple)
        and len(args) == len(default_instance)
    ):
        typ = Tuple[
            tuple(
                _get_type(val_i) if typ_i is Any else typ_i
                for typ_i, val_i in zip(args, default_instance)
            )
        ]  # type: ignore
    return cast(TypeOrCallable, typ)


STRIP_WRAPPER_TYPES = {Final, ReadOnly}

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

        # Search for cycles.
        if seen is None:
            seen = set()
        elif seen is not None and typ in seen:
            # Found a cycle. We don't (currently) support recursive types.
            return typ
        else:
            seen.add(typ)

        # Resolve types recursively.
        return TypeParamResolver._concretize_type_params(typ, seen=seen)

    @staticmethod
    def _concretize_type_params(typ: TypeOrCallable, seen: set[Any]) -> TypeOrCallable:
        """Implementation of concretize_type_params(), which doesn't consider cycles."""
        # Handle aliases.
        typ = resolve_newtype_and_aliases(typ)
        GenericAlias = getattr(types, "GenericAlias", None)
        if GenericAlias is not None and isinstance(typ, GenericAlias):
            type_params = getattr(typ, "__type_params__", ())
            # The __len__ check is for a bug in Python 3.12.0:
            # https://github.com/brentyi/tyro/issues/235
            if hasattr(type_params, "__len__") and len(type_params) != 0:
                type_from_typevar = {}
                for k, v in zip(type_params, get_args(typ)):
                    type_from_typevar[k] = TypeParamResolver._concretize_type_params(
                        v, seen=seen
                    )
                typ = typ.__value__  # type: ignore
                with TypeParamAssignmentContext(typ, type_from_typevar):
                    return TypeParamResolver._concretize_type_params(typ, seen=seen)

        # Search for type parameter assignments.
        for type_from_typevar in reversed(TypeParamResolver.param_assignments):
            if typ in type_from_typevar:
                return type_from_typevar[typ]  # type: ignore

        # Found a TypeVar that isn't bound.
        if isinstance(cast(Any, typ), TypeVar):
            bound = getattr(typ, "__bound__", None)
            if bound is not None:
                # Try to infer type from TypeVar bound.
                warnings.warn(
                    f"Could not resolve type parameter {typ}. Type parameter resolution is not always possible in @staticmethod or @classmethod."
                )
                return bound

            constraints = getattr(typ, "__constraints__", ())
            if len(constraints) > 0:
                # Try to infer type from TypeVar constraints.
                warnings.warn(
                    f"Could not resolve type parameter {typ}. Type parameter resolution is not always possible in @staticmethod or @classmethod."
                )
                return Union[constraints]  # type: ignore

            warnings.warn(
                f"Could not resolve type parameter {typ}. Type parameter resolution is not always possible in @staticmethod or @classmethod."
            )
            return Any  # type: ignore

        origin = get_origin(typ)
        args = get_args(typ)
        if len(args) > 0:
            if origin is Annotated:
                args = args[:1]
            if origin is collections.abc.Callable and isinstance(args[0], list):
                args = tuple(args[0]) + args[1:]

            new_args_list = []
            for x in args:
                for type_from_typevar in reversed(TypeParamResolver.param_assignments):
                    if x in type_from_typevar:
                        x = type_from_typevar[x]
                        break
                new_args_list.append(x)

            new_args = tuple(
                TypeParamResolver.concretize_type_params(
                    # We copy `seen` here to make sure inner types don't impact
                    # each other. This is necessary because `seen` is mutated
                    # in recursive calls; this is not ideal from a robustness
                    # perspective, but convenient for performance reasons.
                    x,
                    seen=seen.copy() if len(new_args_list) > 1 else seen,
                )
                for x in new_args_list
            )

            # Standard generic aliases have a `copy_with()`!
            if origin is UnionType:
                return Union[new_args]  # type: ignore
            elif hasattr(typ, "copy_with"):
                # typing.List, typing.Dict, etc.
                # `.copy_with((a, b, c, d))` on a Callable type will return `Callable[[a, b, c], d]`.
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
def expand_union_types(typ: TypeOrCallable, default_instance: Any) -> TypeOrCallable:
    """Expand union types if necessary.

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
            return Union[options + (type(default_instance),)]  # type: ignore
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

    if len(annotations) == 0:
        return typ, type_from_typevar
    else:
        return (
            Annotated[(typ, *annotations)],  # type: ignore
            type_from_typevar,
        )


def get_type_hints_resolve_type_params(
    obj: Callable[..., Any],
    include_extras: bool = False,
) -> Dict[str, Any]:
    """Variant of `typing.get_type_hints()` that resolves type parameters."""
    if not inspect.isclass(obj):
        if inspect.ismethod(obj):
            bound_instance = getattr(obj, "__self__")
            if inspect.isclass(bound_instance):
                # Class method.
                cls = bound_instance
            else:
                # Instance method.
                if hasattr(bound_instance, "__orig_class__"):
                    # Generic class with bound type parameters.
                    cls = bound_instance.__orig_class__
                else:
                    # No bound type parameters.
                    cls = bound_instance.__class__
            del bound_instance
            unbound_func = getattr(obj, "__func__")
            unbound_func_name = unbound_func.__name__

            # Get class that method was defined in.
            unbound_func_context_cls = None
            for base_cls in cls.mro():
                if unbound_func_name in base_cls.__dict__:
                    unbound_func_context_cls = base_cls
                    break
            assert unbound_func_context_cls is not None

            # Recursively resolve type parameters, until we reach the class
            # that the method is defined in.
            #
            # This is very similar to the type parameter resolution logic that
            # we use for __init__ methods in _fields.py.
            #
            # We should consider refactoring.
            def get_hints_for_bound_method(cls) -> Dict[str, Any]:
                typevar_context = TypeParamResolver.get_assignment_context(cls)
                cls = typevar_context.origin_type
                with typevar_context:
                    if cls is unbound_func_context_cls:
                        return get_type_hints_resolve_type_params(
                            unbound_func, include_extras=include_extras
                        )
                    for base_cls in get_original_bases(cls):
                        if not issubclass(
                            unwrap_origin_strip_extras(base_cls),
                            unbound_func_context_cls,
                        ):
                            continue
                        return get_hints_for_bound_method(
                            TypeParamResolver.concretize_type_params(base_cls)
                        )

                assert False, (
                    "Could not find base class containing method definition. This is likely a bug in tyro."
                )

            out = get_hints_for_bound_method(cls)
            return out
        else:
            # Normal function.
            return {
                k: TypeParamResolver.concretize_type_params(v)
                for k, v in _get_type_hints_backported_syntax(
                    obj, include_extras
                ).items()
            }

    # Get type parameter contexts for all superclasses.
    context_from_origin_type: dict[Any, TypeParamAssignmentContext] = {}

    def recurse_superclass_context(obj: Any) -> None:
        if get_origin(obj) is Generic or obj is object:
            return
        context = TypeParamResolver.get_assignment_context(obj)
        if context.origin_type in context_from_origin_type:
            # Already visited. This should be compatible with diamond
            # inheritance patterns like:
            #
            #   object
            #      |
            #      A
            #     / \
            #    B   C
            #     \ /
            #      D
            #
            # A will be visited twice. For consistency with the mro, only the
            # earlier visit will be used. This is relevant when `A` is a
            # parameterized type (A[T]).
            return
        context_from_origin_type[context.origin_type] = context

        try:
            bases = get_original_bases(context.origin_type)
        except TypeError:
            # For example, `TypedDict`.
            return
        for base in bases:  # type: ignore
            recurse_superclass_context(base)

    recurse_superclass_context(obj)

    # Next, we'll resolve type parameters for each class in the mro. We go in
    # reverse order to ensure that earlier classes take precedence.
    out = {}
    for origin_type in reversed(obj.mro()):
        if origin_type not in context_from_origin_type:
            continue
        with context_from_origin_type[origin_type]:
            out.update(
                {
                    k: TypeParamResolver.concretize_type_params(v)
                    for k, v in _get_type_hints_backported_syntax(
                        origin_type, include_extras=include_extras
                    ).items()
                    if k in origin_type.__dict__.get("__annotations__", {})
                }
            )

    return out


def _get_type_hints_backported_syntax(
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


def is_instance(typ: Any, value: Any) -> bool:
    """Typeguard-based alternative for `isinstance()`."""
    try:
        typeguard.check_type(value, typ)
        return True
    except (typeguard.TypeCheckError, TypeError):
        return False
