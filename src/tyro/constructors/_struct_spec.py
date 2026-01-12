from __future__ import annotations

import collections.abc
import dataclasses
import enum
import functools
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Sequence, Sized

from typing_extensions import cast, get_args, get_origin, is_typeddict

from tyro._typing_compat import is_typing_notrequired, is_typing_required
from tyro.constructors._primitive_spec import (
    PrimitiveTypeInfo,
    UnsupportedTypeAnnotationError,
)

from .. import _docstrings, _resolver
from .. import _fmtlib as fmt
from .._singleton import (
    EXCLUDE_FROM_CALL,
    MISSING,
    MISSING_NONPROP,
    is_missing,
)
from .._typing import TypeForm
from ..conf import _confstruct, _markers

if TYPE_CHECKING:
    from ._registry import ConstructorRegistry


@dataclasses.dataclass(frozen=True)
class UnsupportedStructTypeMessage:
    """Reason why a callable cannot be treated as a struct type."""

    message: str


@dataclasses.dataclass(frozen=True)
class InvalidDefaultInstanceError:
    """Return value when a default instance is not applicable to an annotated struct type."""

    message: tuple[fmt._Text, ...]


@dataclasses.dataclass(frozen=True)
class StructFieldSpec:
    """Behavior specification for a single field in our callable."""

    name: str
    """The name of the field. This will be used as a keyword argument for the
    struct's associated ``instantiate(**kwargs)`` function."""
    type: TypeForm
    """The type of the field. Can be either a primitive or a nested struct type."""
    default: Any
    """The default value of the field."""
    helptext: str | Callable[[], str | None] | None = None
    """Helpjext for the field."""
    # TODO: it's theoretically possible to override the argname with `None`.
    _call_argname: Any = None
    """Private: the name of the argument to pass to the callable. This is used
    for dictionary types."""
    is_default_overridden: None = None
    """Deprecated. No longer used."""


@dataclasses.dataclass(frozen=True)
class StructConstructorSpec:
    """Specification for a struct type, which is broken down into multiple
    fields.

    Each struct type is instantiated by calling an ``instantiate(**kwargs)``
    function with keyword a set of keyword arguments.

    Unlike :class:`PrimitiveConstructorSpec`, there is only one way to use this class.
    It must be returned by a rule in :class:`ConstructorRegistry`.
    """

    instantiate: Callable[..., Any]
    """Function to call to instantiate the struct."""
    fields: tuple[StructFieldSpec, ...]
    """Fields used to construct the callable. Each field is used as a keyword
    argument for the ``instantiate(**kwargs)`` function."""


@dataclasses.dataclass(frozen=True)
class StructTypeInfo:
    """Information used to generate constructors for struct types."""

    type: TypeForm
    """The type of the (potential) struct."""
    markers: tuple[Any, ...]
    """Markers from :mod:`tyro.conf` that are associated with this field."""
    default: Any
    """The default value of the struct, or a member of
    :data:`tyro.constructors.MISSING_AND_MISSING_NONPROP` if not present. In a
    function signature, this is ``X`` in ``def main(x=X): ...``. This can be
    useful for populating the default values of the struct."""
    _typevar_context: _resolver.TypeParamAssignmentContext
    in_union_context: bool
    """Flag indicating whether this type is being evaluated as part of a union.
    When True, allows collection types like List[Struct] or Dict[str, Struct]
    without defaults to be treated as struct types for subcommand creation."""

    @staticmethod
    def make(
        f: TypeForm | Callable, default: Any, in_union_context: bool
    ) -> StructTypeInfo:
        _, parent_markers = _resolver.unwrap_annotated(f, _markers._Marker)
        f, found_subcommand_configs = _resolver.unwrap_annotated(
            f, _confstruct._SubcommandConfig
        )

        # Apply default from subcommand config, but only if no default was passed in to `StructTypeInfo.make()`.
        #
        # If we have a subcommand that's annotated with:
        #
        #     x: (
        #       Annotated[SomeType1, subcommand(default=SomeType1("default1"))]
        #       | Annotated[SomeType2, subcommand(default=SomeType2("default2"))]
        #     ) = SomeType1("assignment1")
        #
        # The assigned default "assignment1" will be routed the `default`
        # argument of this function. The annotated defaults should be captured
        # in `found_subcommand_configs`.
        #
        # For the first subcommand, we should use the default from
        # "assignment1" and not "default1".
        #
        # We'll also use StructTypeInfo for default subcommand matching. This
        # won't work if we always overwrite the assigned default with the one
        # in the annotation.
        if is_missing(default) and len(found_subcommand_configs) > 0:
            default = found_subcommand_configs[0].default

        # Handle generics.
        typevar_context = _resolver.TypeParamResolver.get_assignment_context(f)
        f = typevar_context.origin_type
        f = _resolver.narrow_subtypes(f, default)
        f = _resolver.narrow_collection_types(f, default)

        return StructTypeInfo(
            cast(TypeForm, f),
            parent_markers,
            default,
            typevar_context,
            in_union_context,
        )


def apply_default_struct_rules(registry: ConstructorRegistry) -> None:
    """Apply default struct rules to the registry.

    This function registers all the struct rules for different types:
    - Dataclasses
    - TypedDict
    - Attrs classes
    - Dict
    - NamedTuple
    - Sequences
    - Tuples
    - Pydantic models
    """
    from .._fields import is_struct_type
    from ._struct_spec_attrs import attrs_rule
    from ._struct_spec_dataclass import dataclass_rule
    from ._struct_spec_ml_collections import ml_collections_rule
    from ._struct_spec_msgspec import msgspec_rule
    from ._struct_spec_pydantic import pydantic_rule

    # Register imported rules.
    registry.struct_rule(attrs_rule)
    registry.struct_rule(dataclass_rule)
    registry.struct_rule(ml_collections_rule)
    registry.struct_rule(msgspec_rule)
    registry.struct_rule(pydantic_rule)

    @registry.struct_rule
    def typeddict_rule(info: StructTypeInfo) -> StructConstructorSpec | None:
        # Is this a TypedDict?
        if not is_typeddict(info.type):
            return None

        cls = cast(type, info.type)

        # Handle TypedDicts.
        field_list = []
        valid_default_instance = (
            not is_missing(info.default) and info.default is not EXCLUDE_FROM_CALL
        )
        assert not valid_default_instance or isinstance(info.default, dict)
        total = getattr(cls, "__total__", True)
        assert isinstance(total, bool)
        assert not valid_default_instance or isinstance(info.default, dict)
        for name, typ in _resolver.get_type_hints_resolve_type_params(
            cls, include_extras=True
        ).items():
            typ_origin = get_origin(typ)

            # Unwrap Required[]/NotRequired[] early so we can check the inner type.
            if is_typing_required(typ_origin) or is_typing_notrequired(typ_origin):
                args = get_args(typ)
                assert len(args) == 1, (
                    "typing.Required[] and typing.NotRequired[T] require a concrete type T."
                )
                inner_typ = args[0]
                del args
            else:
                inner_typ = typ

            if valid_default_instance and name in cast(dict, info.default):
                default = cast(dict, info.default)[name]
            elif is_typing_required(typ_origin) and total is False:
                # Support total=False.
                default = MISSING
            elif total is False:
                # Support total=False.
                default = EXCLUDE_FROM_CALL
                if is_struct_type(inner_typ, MISSING_NONPROP, in_union_context=False):
                    # total=False behavior is unideal for nested structures.
                    pass
                    # raise _instantiators.UnsupportedTypeAnnotationError(
                    #     "`total=False` not supported for nested structures."
                    # )
            elif is_typing_notrequired(typ_origin):
                # Support typing.NotRequired[].
                default = EXCLUDE_FROM_CALL
            else:
                default = MISSING

            # Nested struct types need to be populated / can't be excluded from the call.
            # Note: Union types are NOT converted here - they create subparsers that
            # can be optional. When a union field has EXCLUDE_FROM_CALL as its default
            # (from TypedDict total=False or NotRequired[]), no subcommand needs to be
            # selected, and the field will be excluded from the result.
            if default is EXCLUDE_FROM_CALL and is_struct_type(
                inner_typ, MISSING_NONPROP, in_union_context=False
            ):
                default = MISSING_NONPROP

            field_list.append(
                StructFieldSpec(
                    name=name,
                    type=inner_typ,
                    default=default,
                    helptext=functools.partial(
                        _docstrings.get_field_docstring, cls, name, info.markers
                    ),
                )
            )
        return StructConstructorSpec(instantiate=info.type, fields=tuple(field_list))

    @registry.struct_rule
    def dict_rule(info: StructTypeInfo) -> StructConstructorSpec | None:
        origin = get_origin(info.type)
        args = get_args(info.type)
        if is_typeddict(info.type) or (
            info.type
            not in (
                Dict,
                dict,
                collections.abc.Mapping,
            )
            and origin
            not in (
                dict,
                collections.abc.Mapping,
            )
        ):
            return None

        # Check if we have a dict with struct values but no default.
        has_default = not is_missing(info.default)
        has_empty_default = has_default and len(info.default) == 0

        # No default provided or empty default.
        if not has_default or has_empty_default:
            # If the value type is not a primitive: we can try to treat as a struct.
            # This enables subcommands like `dict[str, SomeStruct] | SomeStruct2`.
            from ._registry import ConstructorRegistry

            if (
                origin in (dict, collections.abc.Mapping)
                and len(args) == 2
                and not ConstructorRegistry._is_primitive_type(
                    args[1], set(info.markers)
                )
            ):
                # Require a default (even an empty one) outside of union context.
                if not has_default and not info.in_union_context:
                    from .. import _fmtlib as fmt

                    raise UnsupportedTypeAnnotationError(
                        (
                            fmt.text(
                                "Type ",
                                fmt.text["cyan"](str(info.type)),
                                " with struct-type values requires a default value.",
                            ),
                        )
                    )
                # Allow empty defaults in union context, or when we have any default.
                return StructConstructorSpec(instantiate=dict, fields=())
            return None

        field_list = []
        for k, v in info.default.items():
            field_list.append(
                StructFieldSpec(
                    name=str(k) if not isinstance(k, enum.Enum) else k.name,
                    type=type(v),
                    default=v,
                    helptext=None,
                    _call_argname=k,
                )
            )
        return StructConstructorSpec(instantiate=dict, fields=tuple(field_list))

    @registry.struct_rule
    def namedtuple_rule(info: StructTypeInfo) -> StructConstructorSpec | None:
        if not _resolver.is_namedtuple(info.type):
            return None

        field_list = []
        field_defaults = getattr(info.type, "_field_defaults", {})
        field_names = getattr(info.type, "_fields", [])

        # Handle collections.namedtuple which doesn't have type annotations.
        type_hints = {field: Any for field in field_names}
        type_hints.update(
            _resolver.get_type_hints_resolve_type_params(info.type, include_extras=True)
        )
        for name, typ in type_hints.items():
            default = field_defaults.get(name, MISSING_NONPROP)

            if not is_missing(info.default) and hasattr(info.default, name):
                default = getattr(info.default, name)
            elif info.default is MISSING:
                default = MISSING

            field_list.append(
                StructFieldSpec(
                    name=name,
                    type=typ,  # type: ignore
                    default=default,
                    helptext=functools.partial(
                        _docstrings.get_field_docstring, info.type, name, info.markers
                    ),
                )
            )

        return StructConstructorSpec(instantiate=info.type, fields=tuple(field_list))

    @registry.struct_rule
    def variable_length_sequence_rule(
        info: StructTypeInfo,
    ) -> StructConstructorSpec | None:
        origin = get_origin(info.type)
        if origin not in (
            list,
            set,
            tuple,
            Sequence,
            collections.abc.Sequence,
        ):
            return None

        # Check if we have a collection with struct values but no default.
        has_default = not is_missing(info.default)
        has_empty_default = (
            has_default and isinstance(info.default, Sized) and len(info.default) == 0
        )

        # No default provided or empty default.
        if not has_default or has_empty_default:
            # If the contained type is not a primitive, we can try to treat as a struct.
            # This enables subcommands like `list[SomeStruct] | None`.
            args = get_args(info.type)
            if len(args) == 0:
                return None

            contained_type = cast(type, args[0])

            from ._registry import ConstructorRegistry

            if not ConstructorRegistry._is_primitive_type(
                contained_type, set(info.markers)
            ):
                # Contained type is not a primitive, so treat as struct.
                # Require a default (even an empty one) outside of union context.
                if not has_default and not info.in_union_context:
                    from .. import _fmtlib as fmt

                    raise UnsupportedTypeAnnotationError(
                        (
                            fmt.text(
                                "Type ",
                                fmt.text["cyan"](str(info.type)),
                                " with struct-type values requires a default value.",
                            ),
                        )
                    )

                # Allow empty defaults in union context, or when we have any default.
                if origin is tuple:
                    return StructConstructorSpec(instantiate=tuple, fields=())
                elif origin in (list, Sequence, collections.abc.Sequence):
                    return StructConstructorSpec(instantiate=list, fields=())
                elif origin is set:
                    return StructConstructorSpec(instantiate=set, fields=())
            return None

        # Default is not iterable or not empty - let the rest of the function handle it.
        if not isinstance(info.default, Iterable):
            return None

        # Cast is for mypy.
        contained_type = cast(
            type, get_args(info.type)[0] if get_args(info.type) else Any
        )

        # If the inner type is a primitive, we'll just treat the whole type as
        # a primitive.
        from ._registry import (
            ConstructorRegistry,
            PrimitiveConstructorSpec,
            PrimitiveTypeInfo,
        )

        contained_primitive_spec = ConstructorRegistry.get_primitive_spec(
            PrimitiveTypeInfo.make(contained_type, set(info.markers))
        )
        if (
            isinstance(contained_primitive_spec, PrimitiveConstructorSpec)
            # Why do we check nargs?
            # Because for primitives, we can't nest variable-length collections.
            #
            # For example, list[list[str]] can't be parsed as a single primitive.
            #
            # However, list[list[str]] can be parsed if the outer type is
            # handled as a struct (and a default value is provided, which we
            # check above).
            and contained_primitive_spec.nargs != "*"
        ):
            return None

        field_list = []
        for i, default_i in enumerate(info.default):
            field_list.append(
                StructFieldSpec(
                    name=str(i),
                    type=cast(type, contained_type),
                    default=default_i,
                    helptext="",
                )
            )

        return StructConstructorSpec(
            instantiate=type(info.default), fields=tuple(field_list)
        )

    @registry.struct_rule
    def tuple_rule(info: StructTypeInfo) -> StructConstructorSpec | None:
        # It's important that this tuple rule is defined *after* the general sequence rule. It should take precedence.
        if info.type is not tuple and get_origin(info.type) is not tuple:
            return None

        # Fixed-length tuples.
        children = get_args(info.type)
        if Ellipsis in children:
            return None  # We don't handle variable-length tuples here

        # Infer more specific type when tuple annotation isn't subscripted.
        if len(children) == 0:
            if is_missing(info.default):
                return None
            else:
                assert isinstance(info.default, tuple)
                children = tuple(type(x) for x in info.default)

        if is_missing(info.default) or info.default is EXCLUDE_FROM_CALL:
            default_instance = (info.default,) * len(children)
        else:
            default_instance = info.default

        field_list: list[StructFieldSpec] = []
        for i, child in enumerate(children):
            default_i = default_instance[i]
            field_list.append(
                StructFieldSpec(
                    name=str(i),
                    type=child,
                    default=default_i,
                    helptext="",
                )
            )

        from ._registry import ConstructorRegistry

        # If the tuple only contains primitive types, we can just treat the
        # whole tuple as a primitive.
        #
        # We carve an exception when there are variable-length inner types, like
        # `tuple[list[int], list[str]]`.
        primitive_only = True
        for field in field_list:
            spec = ConstructorRegistry.get_primitive_spec(
                PrimitiveTypeInfo.make(field.type, set(info.markers))
            )
            if isinstance(spec, UnsupportedTypeAnnotationError) or spec.nargs == "*":
                primitive_only = False
                break

        if primitive_only:
            return None
        return StructConstructorSpec(instantiate=tuple, fields=tuple(field_list))
