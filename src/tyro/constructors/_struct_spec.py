from __future__ import annotations

import collections.abc
import dataclasses
import enum
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Sequence

from typing_extensions import (
    NotRequired,
    Required,
    cast,
    get_args,
    get_origin,
    is_typeddict,
)

from tyro.constructors._primitive_spec import (
    PrimitiveTypeInfo,
    UnsupportedTypeAnnotationError,
)

from .. import _docstrings, _resolver
from .._singleton import (
    EXCLUDE_FROM_CALL,
    MISSING,
    MISSING_AND_MISSING_NONPROP,
    MISSING_NONPROP,
)
from .._typing import TypeForm
from ..conf import _confstruct, _markers

if TYPE_CHECKING:
    from ._registry import ConstructorRegistry


@dataclasses.dataclass(frozen=True)
class UnsupportedStructTypeMessage:
    """Reason why a callable cannot be treated as a struct type."""

    message: str


class InvalidDefaultInstanceError(Exception):
    """Raised when a default instance is not applicable to an annoated struct type."""

    def __init__(self, message: str):
        super().__init__(message)


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
    helptext: str | None = None
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

    @staticmethod
    def make(f: TypeForm | Callable, default: Any) -> StructTypeInfo:
        _, parent_markers = _resolver.unwrap_annotated(f, _markers._Marker)
        f = _resolver.swap_type_using_confstruct(f)
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
        if default in MISSING_AND_MISSING_NONPROP and len(found_subcommand_configs) > 0:
            default = found_subcommand_configs[0].default

        # Handle generics.
        typevar_context = _resolver.TypeParamResolver.get_assignment_context(f)
        f = typevar_context.origin_type
        f = _resolver.narrow_subtypes(f, default)
        f = _resolver.narrow_collection_types(f, default)

        return StructTypeInfo(
            cast(TypeForm, f), parent_markers, default, typevar_context
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
            info.default not in MISSING_AND_MISSING_NONPROP
            and info.default is not EXCLUDE_FROM_CALL
        )
        assert not valid_default_instance or isinstance(info.default, dict)
        total = getattr(cls, "__total__", True)
        assert isinstance(total, bool)
        assert not valid_default_instance or isinstance(info.default, dict)
        for name, typ in _resolver.get_type_hints_resolve_type_params(
            cls, include_extras=True
        ).items():
            typ_origin = get_origin(typ)
            if valid_default_instance and name in cast(dict, info.default):
                default = cast(dict, info.default)[name]
            elif typ_origin is Required and total is False:
                # Support total=False.
                default = MISSING
            elif total is False:
                # Support total=False.
                default = EXCLUDE_FROM_CALL
                if is_struct_type(typ, MISSING_NONPROP):
                    # total=False behavior is unideal for nested structures.
                    pass
                    # raise _instantiators.UnsupportedTypeAnnotationError(
                    #     "`total=False` not supported for nested structures."
                    # )
            elif typ_origin is NotRequired:
                # Support typing.NotRequired[].
                default = EXCLUDE_FROM_CALL
            else:
                default = MISSING

            # Nested types need to be populated / can't be excluded from the call.
            if default is EXCLUDE_FROM_CALL and is_struct_type(typ, MISSING_NONPROP):
                default = MISSING_NONPROP

            if typ_origin in (Required, NotRequired):
                args = get_args(typ)
                assert len(args) == 1, (
                    "typing.Required[] and typing.NotRequired[T] require a concrete type T."
                )
                typ = args[0]
                del args

            field_list.append(
                StructFieldSpec(
                    name=name,
                    type=typ,
                    default=default,
                    helptext=_docstrings.get_field_docstring(cls, name, info.markers),
                )
            )
        return StructConstructorSpec(instantiate=info.type, fields=tuple(field_list))

    @registry.struct_rule
    def dict_rule(info: StructTypeInfo) -> StructConstructorSpec | None:
        if is_typeddict(info.type) or (
            info.type
            not in (
                Dict,
                dict,
                collections.abc.Mapping,
            )
            and get_origin(info.type)
            not in (
                dict,
                collections.abc.Mapping,
            )
        ):
            return None

        if info.default in MISSING_AND_MISSING_NONPROP or len(info.default) == 0:
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

            if info.default not in MISSING_AND_MISSING_NONPROP and hasattr(
                info.default, name
            ):
                default = getattr(info.default, name)
            elif info.default is MISSING:
                default = MISSING

            field_list.append(
                StructFieldSpec(
                    name=name,
                    type=typ,  # type: ignore
                    default=default,
                    helptext=_docstrings.get_field_docstring(
                        info.type, name, info.markers
                    ),
                )
            )

        return StructConstructorSpec(instantiate=info.type, fields=tuple(field_list))

    @registry.struct_rule
    def variable_length_sequence_rule(
        info: StructTypeInfo,
    ) -> StructConstructorSpec | None:
        if get_origin(info.type) not in (
            list,
            set,
            tuple,
            Sequence,
            collections.abc.Sequence,
        ) or not isinstance(info.default, Iterable):
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
            if info.default in MISSING_AND_MISSING_NONPROP:
                return None
            else:
                assert isinstance(info.default, tuple)
                children = tuple(type(x) for x in info.default)

        if (
            info.default in MISSING_AND_MISSING_NONPROP
            or info.default is EXCLUDE_FROM_CALL
        ):
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
