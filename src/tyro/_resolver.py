"""Resolver utilities: type unwrapping, narrowing, and TypeVar resolution."""

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
    Dict,
    List,
    Literal,
    Mapping,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)
from typing import Type as TypeForm

from typing_extensions import (
    Annotated,
    ForwardRef,
    NoDefault,
    Self,
    TypeAliasType,
    get_args,
    get_origin,
    get_original_bases,
    get_type_hints,
)

from . import _unsafe_cache
from ._singleton import is_missing, is_sentinel
from ._typing_compat import (
    is_typing_annotated,
    is_typing_classvar,
    is_typing_final,
    is_typing_generic,
    is_typing_protocol,
    is_typing_readonly,
    is_typing_typealiastype,
    is_typing_union,
)
from ._warnings import TyroWarning
from .conf import _confstruct

TypeOrCallable = TypeVar("TypeOrCallable", TypeForm[Any], Callable)
TypeOrCallableOrNone = TypeVar("TypeOrCallableOrNone", Callable, TypeForm[Any], None)
MetadataType = TypeVar("MetadataType")

UnionType = getattr(types, "UnionType", Union)
"""Same as types.UnionType, but points to typing.Union for older versions of Python."""


# =============================================================================
# Unwrap utilities
# =============================================================================


@dataclasses.dataclass(frozen=True)
class TyroTypeAliasBreadCrumb:
    """Breadcrumb to track names of type aliases and NewType for subcommands."""

    name: str


def unwrap_origin_strip_extras(typ: TypeOrCallable) -> TypeOrCallable:
    """Returns the origin of typ, ignoring Annotated, or typ itself if no origin."""
    typ = unwrap_annotated(typ)
    origin = get_origin(typ)
    if origin is not None:
        typ = origin
    return typ


def resolve_newtype_and_aliases(typ: TypeOrCallableOrNone) -> TypeOrCallableOrNone:
    """Resolve NewType and TypeAliasType, adding TyroTypeAliasBreadCrumb annotations."""
    if type(typ) is type:
        return typ
    # Handle type aliases (Python 3.12+ `type` statement).
    if is_typing_typealiastype(type(typ)):
        typ_cast = cast(TypeAliasType, typ)
        return Annotated[  # type: ignore
            (
                cast(Any, resolve_newtype_and_aliases(typ_cast.__value__)),
                TyroTypeAliasBreadCrumb(typ_cast.__name__),
            )
        ]
    # Unwrap NewType via duck typing (NewType isn't a class until Python 3.10).
    return_name = None
    while hasattr(typ, "__name__") and hasattr(typ, "__supertype__"):
        if return_name is None:
            return_name = getattr(typ, "__name__")
        typ = resolve_newtype_and_aliases(getattr(typ, "__supertype__"))
    if return_name is not None:
        typ = Annotated[(typ, TyroTypeAliasBreadCrumb(return_name))]  # type: ignore
    return cast(TypeOrCallableOrNone, typ)


@overload
def unwrap_annotated(
    typ: Any, search_type: TypeForm[MetadataType]
) -> Tuple[Any, Tuple[MetadataType, ...]]: ...
@overload
def unwrap_annotated(
    typ: Any, search_type: Literal["all"]
) -> Tuple[Any, Tuple[Any, ...]]: ...
@overload
def unwrap_annotated(typ: Any, search_type: None = None) -> Any: ...


def unwrap_annotated(
    typ: Any,
    search_type: Union[TypeForm[MetadataType], Literal["all"], object, None] = None,
) -> Union[Tuple[Any, Tuple[MetadataType, ...]], Any]:
    """Strip Annotated and extract metadata. Examples:
    - int => int (or (int, ()) with search_type)
    - Annotated[int, 1], int => (int, (1,))
    - Annotated[int, "1"], int => (int, ())
    """
    # Fast path for plain types.
    if isinstance(typ, type):
        if search_type is None:
            return typ
        elif not hasattr(typ, "__tyro_markers__"):
            return typ, ()

    typ = resolve_newtype_and_aliases(typ)

    # Final and ReadOnly types are ignored in tyro.
    orig = get_origin(typ)
    while is_typing_final(orig) or is_typing_readonly(orig):
        typ = get_args(typ)[0]
        orig = get_origin(typ)

    if search_type is None:
        if not hasattr(typ, "__metadata__"):
            return typ
        else:
            return get_args(typ)[0]

    # Check for __tyro_markers__ from @configure.
    if hasattr(typ, "__dict__") and "__tyro_markers__" in typ.__dict__:
        targets = tuple(
            x
            for x in typ.__dict__["__tyro_markers__"]
            if search_type == "all" or isinstance(x, search_type)  # type: ignore
        )
    else:
        targets = ()

    assert isinstance(targets, tuple)
    if not hasattr(typ, "__metadata__"):
        return typ, targets  # type: ignore

    args = get_args(typ)
    assert len(args) >= 2
    targets += tuple(
        x
        for x in targets + args[1:]
        if search_type == "all" or isinstance(x, search_type)  # type: ignore
    )
    if hasattr(args[0], "__tyro_markers__"):
        targets += tuple(
            x
            for x in getattr(args[0], "__tyro_markers__")
            if search_type == "all" or isinstance(x, search_type)  # type: ignore
        )
    return args[0], targets  # type: ignore


def swap_type_using_confstruct(typ: TypeOrCallable) -> TypeOrCallable:
    """Swap types using constructor_factory from tyro.conf.arg/subcommand."""
    _, annotations = unwrap_annotated(typ, search_type="all")
    for anno in reversed(annotations):
        if (
            isinstance(anno, (_confstruct._ArgConfig, _confstruct._SubcommandConfig))
            and anno.constructor_factory is not None
        ):
            return Annotated[(anno.constructor_factory(),) + annotations]  # type: ignore
    return typ


# =============================================================================
# Type narrowing
# =============================================================================


@_unsafe_cache.unsafe_cache(maxsize=1024)
def narrow_subtypes(typ: TypeOrCallable, default_instance: Any) -> TypeOrCallable:
    """Type narrowing: if annotated as Animal but default is Cat, parse as Cat.
    Only for nested structures, not individual fields."""
    typ = resolve_newtype_and_aliases(typ)
    if is_missing(default_instance):
        return typ
    try:
        potential_subclass = type(default_instance)
        if potential_subclass is type:
            return typ
        superclass = unwrap_annotated(typ)
        if is_typing_union(get_origin(superclass)):
            return typ
        if superclass is Any or issubclass(potential_subclass, superclass):  # type: ignore
            if is_typing_annotated(get_origin(typ)):
                return Annotated[(potential_subclass,) + get_args(typ)[1:]]  # type: ignore
            typ = cast(TypeOrCallable, potential_subclass)
    except TypeError:
        pass
    return typ


def narrow_collection_types(
    typ: TypeOrCallable, default_instance: Any
) -> TypeOrCallable:
    """Narrow container types by inferring element types from defaults."""
    if is_missing(default_instance):
        return typ

    def _get_type(val: Any) -> TypeForm:
        return narrow_collection_types(type(val), val)

    args = get_args(typ)
    origin = get_origin(typ)
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


@_unsafe_cache.unsafe_cache(maxsize=1024)
def expand_union_types(typ: TypeOrCallable, default_instance: Any) -> TypeOrCallable:
    """Expand union if default doesn't match any member (with warning)."""
    if not is_typing_union(get_origin(typ)):
        return typ
    options = get_args(typ)
    options_unwrapped = [unwrap_origin_strip_extras(o) for o in options]
    try:
        if not is_sentinel(default_instance) and not any(
            isinstance_with_fuzzy_numeric_tower(default_instance, o) is not False
            for o in options_unwrapped
        ):
            warnings.warn(
                f"{type(default_instance)} does not match any type in Union:"
                f" {options_unwrapped}",
                category=TyroWarning,
            )
            return Union[options + (type(default_instance),)]  # type: ignore
    except TypeError:
        pass
    return typ


# =============================================================================
# Type inspection utilities
# =============================================================================


def is_dataclass(cls: Any) -> bool:
    """Same as dataclasses.is_dataclass, but handles generic aliases."""
    return dataclasses.is_dataclass(unwrap_origin_strip_extras(cls))  # type: ignore


def resolved_fields(cls: Type) -> List[dataclasses.Field]:
    """Like dataclasses.fields(), but includes InitVar and resolves forward refs."""
    assert dataclasses.is_dataclass(cls)
    fields = []
    annotations = get_type_hints_resolve_type_params(
        cast(Callable, cls), include_extras=True
    )
    for field in getattr(cls, "__dataclass_fields__").values():
        field = copy.copy(field)
        field.type = annotations[field.name]
        if is_typing_classvar(get_origin(field.type)):
            continue
        if isinstance(field.type, dataclasses.InitVar):
            field.type = field.type.type
        fields.append(field)
    return fields


def is_namedtuple(cls: Any) -> bool:
    """Check if type is a namedtuple."""
    return (
        isinstance(cls, type)
        and issubclass(cls, tuple)
        and hasattr(cls, "_fields")
        and hasattr(cls, "_asdict")
    )


def is_instance(typ: Any, value: Any) -> bool:
    """Typeguard-based isinstance() for complex types."""
    if type(typ) is type:
        return isinstance(value, typ)
    origin = get_origin(typ)
    if origin is Union:
        return any(is_instance(arg, value) for arg in get_args(typ))
    if origin is Annotated:
        args = get_args(typ)
        if args:
            return is_instance(args[0], value)
    if origin is Literal:
        return value in get_args(typ)
    import typeguard

    try:
        typeguard.check_type(value, typ)
        return True
    except (typeguard.TypeCheckError, TypeError):
        return False


def isinstance_with_fuzzy_numeric_tower(
    obj: Any, classinfo: Type
) -> Union[bool, Literal["~"]]:
    """isinstance() with numeric tower awareness. Returns True (exact), "~" (compatible), or False."""
    if isinstance(obj, classinfo):
        return True
    if isinstance(obj, bool):
        if classinfo in (int, float, complex):
            return "~"
    elif isinstance(obj, int) and not isinstance(obj, bool):
        if classinfo in (float, complex):
            return "~"
    elif isinstance(obj, float):
        if classinfo is complex:
            return "~"
    return False


# =============================================================================
# TypeVar resolution
# =============================================================================

_param_assignments: List[Dict[TypeVar, TypeForm[Any]]] = []


@dataclasses.dataclass(frozen=True)
class TypeParamAssignmentContext:
    """Context manager for TypeVar assignments during type resolution."""

    origin_type: Any
    type_from_typevar: Mapping[TypeVar, TypeForm[Any]]

    def __enter__(self) -> None:
        if len(self.type_from_typevar) > 0:
            TypeParamResolver.param_assignments.append(dict(self.type_from_typevar))

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        if len(self.type_from_typevar) > 0:
            TypeParamResolver.param_assignments.pop()


class TypeParamResolver:
    """Static methods for TypeVar resolution."""

    param_assignments: List[Dict[TypeVar, TypeForm[Any]]] = _param_assignments

    @classmethod
    def get_assignment_context(cls, typ: TypeOrCallable) -> TypeParamAssignmentContext:
        """Get context manager for resolving type parameters."""
        typ, type_from_typevar = resolve_generic_types(typ)
        return TypeParamAssignmentContext(typ, type_from_typevar)

    @staticmethod
    def resolve_params_and_aliases(
        typ: TypeOrCallable,
        seen: set[Any] | None = None,
        ignore_confstruct: bool = False,
    ) -> TypeOrCallable:
        """Apply type parameter assignments based on current context."""
        if seen is None:
            seen = set()
        elif typ in seen:
            return typ  # Cycle detected.
        else:
            seen.add(typ)
        return TypeParamResolver._resolve_type_params(typ, seen, ignore_confstruct)

    @staticmethod
    def _resolve_type_params(
        typ: TypeOrCallable, seen: set[Any], ignore_confstruct: bool
    ) -> TypeOrCallable:
        """Implementation of resolve_params_and_aliases()."""
        if not ignore_confstruct:
            typ = swap_type_using_confstruct(typ)
        typ = resolve_newtype_and_aliases(typ)

        GenericAlias = getattr(types, "GenericAlias", None)
        if GenericAlias is not None and isinstance(typ, GenericAlias):
            type_params = getattr(typ, "__type_params__", ())
            if hasattr(type_params, "__len__") and len(type_params) != 0:
                type_from_typevar = {}
                for k, v in zip(type_params, get_args(typ)):
                    type_from_typevar[k] = TypeParamResolver._resolve_type_params(
                        v, seen, ignore_confstruct
                    )
                typ = typ.__value__  # type: ignore
                with TypeParamAssignmentContext(typ, type_from_typevar):
                    return TypeParamResolver._resolve_type_params(
                        typ, seen, ignore_confstruct
                    )

        # Search for type parameter assignments.
        for type_from_typevar in reversed(TypeParamResolver.param_assignments):
            if typ in type_from_typevar:
                return type_from_typevar[typ]  # type: ignore

        # Handle unbound TypeVar.
        if isinstance(cast(Any, typ), TypeVar) and get_origin(typ) is None:
            default = getattr(typ, "__default__", NoDefault)
            if default is not NoDefault:
                return default  # type: ignore
            bound = getattr(typ, "__bound__", None)
            if bound is not None:
                warnings.warn(
                    f"Could not resolve type parameter {typ}. Type parameter resolution "
                    "is not always possible in @staticmethod or @classmethod.",
                    category=TyroWarning,
                )
                return bound
            constraints = getattr(typ, "__constraints__", ())
            if len(constraints) > 0:
                warnings.warn(
                    f"Could not resolve type parameter {typ}. Type parameter resolution "
                    "is not always possible in @staticmethod or @classmethod.",
                    category=TyroWarning,
                )
                return Union[constraints]  # type: ignore
            warnings.warn(
                f"Could not resolve type parameter {typ}. Type parameter resolution "
                "is not always possible in @staticmethod or @classmethod.",
                category=TyroWarning,
            )
            return Any  # type: ignore

        args = get_args(typ)
        if len(args) > 0:
            origin = get_origin(typ)
            callable_was_flattened = False
            args_to_process = args
            if is_typing_annotated(origin):
                args_to_process = args[:1]
            if origin is collections.abc.Callable and isinstance(
                args_to_process[0], list
            ):
                args_to_process = tuple(args_to_process[0]) + args_to_process[1:]
                callable_was_flattened = True

            if len(TypeParamResolver.param_assignments) == 0:
                new_args_list = args_to_process
            else:
                new_args_list = []
                for x in args_to_process:
                    for type_from_typevar in reversed(
                        TypeParamResolver.param_assignments
                    ):
                        if x in type_from_typevar:
                            x = type_from_typevar[x]
                            break
                    new_args_list.append(x)

            new_args = tuple(
                TypeParamResolver.resolve_params_and_aliases(
                    x, seen=seen.copy() if len(new_args_list) > 1 else seen
                )
                for x in new_args_list
            )
            if new_args == args_to_process:
                return typ
            if origin is UnionType:
                return Union[new_args]  # type: ignore
            elif hasattr(typ, "copy_with"):
                return typ.copy_with(new_args)  # type: ignore
            elif callable_was_flattened:
                param_types = new_args[:-1]
                return_type = new_args[-1]
                assert origin is not None
                return origin[(list(param_types), return_type)]
            else:
                assert origin is not None
                return origin[new_args]
        return typ  # type: ignore


def resolve_generic_types(
    typ: TypeOrCallable,
) -> Tuple[TypeOrCallable, Dict[TypeVar, TypeForm[Any]]]:
    """Return origin class and typevar->type mapping for generic aliases."""
    annotations: Tuple[Any, ...] = ()
    if is_typing_annotated(get_origin(typ)):
        typ, annotations = unwrap_annotated(typ, "all")

    typ = resolve_newtype_and_aliases(typ)
    origin_cls = get_origin(typ)
    type_from_typevar: Dict[TypeVar, TypeForm[Any]] = {}

    # Support typing.Self.
    if hasattr(typ, "__self__"):
        self_type = getattr(typ, "__self__")
        if inspect.isclass(self_type):
            type_from_typevar[cast(TypeVar, Self)] = self_type  # type: ignore
        else:
            type_from_typevar[cast(TypeVar, Self)] = self_type.__class__  # type: ignore

    # Support pydantic generics.
    pydantic_generic_metadata = getattr(typ, "__pydantic_generic_metadata__", None)
    is_pydantic_generic = False
    if pydantic_generic_metadata is not None:
        args = pydantic_generic_metadata.get("args", ())
        origin_typ = pydantic_generic_metadata.get("origin", None)
        parameters = getattr(origin_typ, "__pydantic_generic_metadata__", {}).get(
            "parameters", ()
        )
        if len(parameters) == len(args):
            is_pydantic_generic = True
            type_from_typevar.update(dict(zip(parameters, args)))

    if (
        not is_pydantic_generic
        and origin_cls is not None
        and hasattr(origin_cls, "__parameters__")
        and hasattr(origin_cls.__parameters__, "__len__")
    ):
        typevars = origin_cls.__parameters__
        typevar_values = get_args(typ)
        assert len(typevars) == len(typevar_values)
        typ = origin_cls
        type_from_typevar.update(dict(zip(typevars, typevar_values)))

    if len(annotations) == 0:
        return typ, type_from_typevar
    else:
        return Annotated[(typ, *annotations)], type_from_typevar  # type: ignore


def get_type_hints_resolve_type_params(
    obj: Callable[..., Any], include_extras: bool = False
) -> Dict[str, Any]:
    """Variant of typing.get_type_hints() that resolves type parameters."""
    if not inspect.isclass(obj):
        if inspect.ismethod(obj):
            bound_instance = getattr(obj, "__self__")
            if inspect.isclass(bound_instance):
                cls = bound_instance
            else:
                if hasattr(bound_instance, "__orig_class__"):
                    cls = bound_instance.__orig_class__
                else:
                    cls = bound_instance.__class__
            del bound_instance
            unbound_func = getattr(obj, "__func__")
            unbound_func_name = unbound_func.__name__
            unbound_func_context_cls = None
            for base_cls in cls.mro():
                if unbound_func_name in base_cls.__dict__:
                    unbound_func_context_cls = base_cls
                    break
            assert unbound_func_context_cls is not None

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
                            TypeParamResolver.resolve_params_and_aliases(base_cls)
                        )
                assert False, "Could not find base class containing method definition."

            return get_hints_for_bound_method(cls)
        else:
            return {
                k: TypeParamResolver.resolve_params_and_aliases(v)
                for k, v in _get_type_hints_backported_syntax(
                    obj, include_extras
                ).items()
            }

    # Get type parameter contexts for all superclasses.
    context_from_origin_type: dict[Any, TypeParamAssignmentContext] = {}

    def recurse_superclass_context(obj: Any) -> None:
        origin_cls = get_origin(obj)
        if (
            is_typing_generic(origin_cls)
            or is_typing_protocol(origin_cls)
            or obj is object
        ):
            return
        context = TypeParamResolver.get_assignment_context(obj)
        if context.origin_type in context_from_origin_type:
            return
        context_from_origin_type[context.origin_type] = context
        try:
            bases = get_original_bases(context.origin_type)
        except TypeError:
            return
        with context:
            resolved_bases = [
                TypeParamResolver.resolve_params_and_aliases(
                    base, ignore_confstruct=True
                )
                for base in bases
            ]
        for base in resolved_bases:
            recurse_superclass_context(base)

    recurse_superclass_context(obj)

    out = {}
    for origin_type in reversed(obj.mro()):
        if origin_type not in context_from_origin_type:
            continue
        raw_hints = _get_type_hints_backported_syntax(
            origin_type, include_extras=include_extras
        )
        if sys.version_info < (3, 14):
            keys = set(origin_type.__dict__.get("__annotations__", {}).keys())
        elif hasattr(origin_type, "__annotations__"):
            keys = set(getattr(origin_type, "__annotations__").keys())
        else:
            keys = set()
        pydantic_generic_metadata = getattr(
            origin_type, "__pydantic_generic_metadata__", None
        )
        if pydantic_generic_metadata is not None:
            keys = keys | set(
                getattr(
                    pydantic_generic_metadata.get("origin", None), "__annotations__", ()
                )
            )
        with context_from_origin_type[origin_type]:
            out.update(
                {
                    k: TypeParamResolver.resolve_params_and_aliases(v)
                    for k, v in raw_hints.items()
                    if k in keys
                }
            )
    return out


def _get_type_hints_backported_syntax(
    obj: Callable[..., Any], include_extras: bool = False
) -> Dict[str, Any]:
    """get_type_hints() with support for X | Y and list[str] in older Python."""
    try:
        return get_type_hints(obj, include_extras=include_extras)
    except TypeError as e:  # pragma: no cover
        if hasattr(obj, "__annotations__"):
            try:
                from eval_type_backport import eval_type_backport

                globalns = getattr(obj, "__globals__", None)
                if globalns is None and hasattr(obj, "__module__"):
                    globalns = sys.modules[getattr(obj, "__module__")].__dict__
                if globalns is None and hasattr(globalns, "__init__"):
                    globalns = getattr(getattr(obj, "__init__"), "__globals__", None)
                return {
                    k: eval_type_backport(ForwardRef(v), globalns=globalns, localns={})
                    for k, v in getattr(obj, "__annotations__").items()
                }
            except ImportError:
                pass
        raise e
