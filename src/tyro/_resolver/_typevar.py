"""TypeVar resolution utilities."""

from __future__ import annotations

import collections.abc
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
    Mapping,
    Tuple,
    TypeVar,
    Union,
    cast,
)
from typing import (
    Type as TypeForm,
)

from typing_extensions import (
    Annotated,
    ForwardRef,
    NoDefault,
    Self,
    get_args,
    get_origin,
    get_original_bases,
    get_type_hints,
)

from .._typing_compat import is_typing_annotated, is_typing_generic, is_typing_protocol
from .._warnings import TyroWarning
from ._unwrap import (
    resolve_newtype_and_aliases,
    swap_type_using_confstruct,
    unwrap_annotated,
    unwrap_origin_strip_extras,
)

UnionType = getattr(types, "UnionType", Union)
"""Same as types.UnionType, but points to typing.Union for older versions of
Python. types.UnionType was added in Python 3.10, and is created when the `X |
Y` syntax is used for unions."""

TypeOrCallable = TypeVar("TypeOrCallable", TypeForm[Any], Callable)

# TypeVar resolution uses a global stack for context.
_param_assignments: List[Dict[TypeVar, TypeForm[Any]]] = []


@dataclasses.dataclass(frozen=True)
class TypeParamAssignmentContext:
    """Context for TypeVar assignments during type resolution.

    This is a frozen dataclass that stores the resolved type and its TypeVar
    assignments. It can be used as a context manager to make the assignments
    available during nested type resolution.

    The context manager methods push/pop to a class-level list, which is fine -
    the context object itself remains immutable.
    """

    origin_type: Any  # TypeOrCallable, but Any needed for mypy compatibility
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
        """Context manager for resolving type parameters."""
        typ, type_from_typevar = resolve_generic_types(typ)
        return TypeParamAssignmentContext(typ, type_from_typevar)

    @staticmethod
    def resolve_params_and_aliases(
        typ: TypeOrCallable,
        seen: set[Any] | None = None,
        ignore_confstruct: bool = False,
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
        return TypeParamResolver._resolve_type_params(
            typ, seen=seen, ignore_confstruct=ignore_confstruct
        )

    @staticmethod
    def _resolve_type_params(
        typ: TypeOrCallable,
        seen: set[Any],
        ignore_confstruct: bool,
    ) -> TypeOrCallable:
        """Implementation of resolve_type_params(), which doesn't consider cycles."""
        # Handle aliases.
        if not ignore_confstruct:
            typ = swap_type_using_confstruct(typ)
        typ = resolve_newtype_and_aliases(typ)
        GenericAlias = getattr(types, "GenericAlias", None)
        if GenericAlias is not None and isinstance(typ, GenericAlias):
            type_params = getattr(typ, "__type_params__", ())
            # The __len__ check is for a bug in Python 3.12.0:
            # https://github.com/brentyi/tyro/issues/235
            if hasattr(type_params, "__len__") and len(type_params) != 0:
                type_from_typevar = {}
                for k, v in zip(type_params, get_args(typ)):
                    type_from_typevar[k] = TypeParamResolver._resolve_type_params(
                        v, seen=seen, ignore_confstruct=ignore_confstruct
                    )
                typ = typ.__value__  # type: ignore
                with TypeParamAssignmentContext(typ, type_from_typevar):
                    return TypeParamResolver._resolve_type_params(
                        typ, seen=seen, ignore_confstruct=ignore_confstruct
                    )

        # Search for type parameter assignments.
        for type_from_typevar in reversed(TypeParamResolver.param_assignments):
            if typ in type_from_typevar:
                return type_from_typevar[typ]  # type: ignore

        # Found a TypeVar that isn't bound.
        # Note: In Python 3.8, Unpack[TypedDict] incorrectly passes isinstance(typ, TypeVar).
        # We exclude types with an origin (like Unpack[...]) since they should be handled
        # by the get_args() code path below.
        if isinstance(cast(Any, typ), TypeVar) and get_origin(typ) is None:
            # Check for TypeVar default (PEP 696, available via typing_extensions).
            default = getattr(typ, "__default__", NoDefault)
            # If __default__ exists and is not the NoDefault sentinel, use it.
            if default is not NoDefault:
                # We have a valid default, use it without warning.
                return default  # type: ignore

            bound = getattr(typ, "__bound__", None)
            if bound is not None:
                # Try to infer type from TypeVar bound.
                warnings.warn(
                    f"Could not resolve type parameter {typ}. Type parameter resolution is not always possible in @staticmethod or @classmethod.",
                    category=TyroWarning,
                )
                return bound

            constraints = getattr(typ, "__constraints__", ())
            if len(constraints) > 0:
                # Try to infer type from TypeVar constraints.
                warnings.warn(
                    f"Could not resolve type parameter {typ}. Type parameter resolution is not always possible in @staticmethod or @classmethod.",
                    category=TyroWarning,
                )
                return Union[constraints]  # type: ignore

            warnings.warn(
                f"Could not resolve type parameter {typ}. Type parameter resolution is not always possible in @staticmethod or @classmethod.",
                category=TyroWarning,
            )
            return Any  # type: ignore

        args = get_args(typ)
        if len(args) > 0:
            origin = get_origin(typ)
            callable_was_flattened = False

            # Filter args based on type.
            #
            # For Annotated types, we only process the first arg (the actual type),
            # not the metadata. The metadata will be preserved automatically by
            # copy_with() later.
            args_to_process = args
            if is_typing_annotated(origin):
                args_to_process = args[:1]
            if origin is collections.abc.Callable and isinstance(
                args_to_process[0], list
            ):
                args_to_process = tuple(args_to_process[0]) + args_to_process[1:]
                callable_was_flattened = True

            # Substitute type parameters if we're in a generic context.
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

            # Recursively resolve type parameters and aliases in the arguments.
            # We copy `seen` for each arg to prevent sibling args from interfering
            # with each other's cycle detection.
            new_args = tuple(
                TypeParamResolver.resolve_params_and_aliases(
                    x, seen=seen.copy() if len(new_args_list) > 1 else seen
                )
                for x in new_args_list
            )

            # Early return if nothing changed.
            if new_args == args_to_process:
                return typ

            # Standard generic aliases have a `copy_with()`!
            if origin is UnionType:
                return Union[new_args]  # type: ignore
            elif hasattr(typ, "copy_with"):
                # typing.List, typing.Dict, etc.
                # `.copy_with((a, b, c, d))` on a Callable type will return `Callable[[a, b, c], d]`.
                return typ.copy_with(new_args)  # type: ignore
            elif callable_was_flattened:
                # Special handling for collections.abc.Callable: need to unflatten args
                # that were flattened above on lines 451-453.
                #
                # Restore the original format: [param_types..., return_type] -> [[param_types...], return_type]
                param_types = new_args[:-1]
                return_type = new_args[-1]
                final_args = (list(param_types), return_type)
                assert origin is not None
                return origin[final_args]
            else:
                # list[], dict[], etc.
                assert origin is not None
                return origin[new_args]

        return typ  # type: ignore


def resolve_generic_types(
    typ: TypeOrCallable,
) -> Tuple[TypeOrCallable, Dict[TypeVar, TypeForm[Any]]]:
    """If the input is a class: no-op. If it's a generic alias: returns the origin
    class, and a mapping from typevars to concrete types."""

    annotations: Tuple[Any, ...] = ()
    if is_typing_annotated(get_origin(typ)):
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

    # Support pydantic: https://github.com/pydantic/pydantic/issues/3559
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
                            TypeParamResolver.resolve_params_and_aliases(base_cls)
                        )

                assert False, (
                    "Could not find base class containing method definition. This is likely a bug in tyro."
                )

            out = get_hints_for_bound_method(cls)
            return out
        else:
            # Normal function.
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

        # Substitution for forwarded type parameters; if we have:
        #     class A[T](Base[T]): ...
        # and we're resolving A[int], the base class should be treated as Base[int].
        #
        # We set `ignore_confstruct=True` to avoid swapping types from
        # `tyro.conf.arg` and `tyro.conf.subcommand`'s `constructor_factory`
        # attributes, which might be applied using the `@tyro.conf.configure`
        # decorator. These attributes should be ignored when traversing
        # inheritance hierarchies.
        with context:
            resolved_bases = [
                TypeParamResolver.resolve_params_and_aliases(
                    base, ignore_confstruct=True
                )
                for base in bases
            ]

        # Recursively resolve type parameters for all bases.
        for base in resolved_bases:  # type: ignore
            recurse_superclass_context(base)

    recurse_superclass_context(obj)

    # Next, we'll resolve type parameters for each class in the mro. We go in
    # reverse order to ensure that earlier classes take precedence.
    out = {}
    for origin_type in reversed(obj.mro()):
        if origin_type not in context_from_origin_type:
            continue

        raw_hints = _get_type_hints_backported_syntax(
            origin_type, include_extras=include_extras
        )

        # Explicit version check avoids an edge case for inherited generics.
        # Specifically: tests/test_nested.py::test_generic_inherited

        # if "__annotations__" in origin_type.__dict__:
        if sys.version_info < (3, 14):
            # Python 3.8~3.13.
            keys = set(origin_type.__dict__.get("__annotations__", {}).keys())
        elif hasattr(origin_type, "__annotations__"):
            # Python 3.14.
            keys = set(getattr(origin_type, "__annotations__").keys())
        else:
            keys = set()

        # Pydantic generics need special handling.
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
                if globalns is None and hasattr(obj, "__module__"):
                    globalns = sys.modules[getattr(obj, "__module__")].__dict__
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
