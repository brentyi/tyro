from __future__ import annotations

import collections.abc
import dataclasses
import enum
import sys
import warnings
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Sequence, Union

from typing_extensions import (
    Annotated,
    NotRequired,
    Required,
    cast,
    get_args,
    get_origin,
    is_typeddict,
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


@dataclasses.dataclass(frozen=True)
class StructFieldSpec:
    """Behavior specification for a single field in our callable."""

    name: str
    """The name of the field. This will be used as a keyword argument for the
    struct's associated `instantiate(**kwargs)` function."""
    type: TypeForm
    """The type of the field. Can be either a primitive or a nested struct type."""
    default: Any
    """The default value of the field."""
    is_default_overridden: bool = False
    """Whether the default value was overridden by the default instance. Should
    be set to False if the default value was assigned by the field itself."""
    helptext: str | None = None
    """Helpjext for the field."""
    # TODO: it's theoretically possible to override the argname with `None`.
    _call_argname: Any = None
    """Private: the name of the argument to pass to the callable. This is used
    for dictionary types."""


@dataclasses.dataclass(frozen=True)
class StructConstructorSpec:
    """Specification for a struct type, which is broken down into multiple
    fields.

    Each struct type is instantiated by calling an `instantiate(**kwargs)`
    function with keyword a set of keyword arguments.

    Unlike `PrimitiveConstructorSpec`, there is only one way to use this class.
    It must be returned by a rule in `ConstructorRegistry`.
    """

    instantiate: Callable[..., Any]
    """Function to call to instantiate the struct."""
    fields: tuple[StructFieldSpec, ...]
    """Fields used to construct the callable. Each field is used as a keyword
    argument for the `instantiate(**kwargs)` function."""


@dataclasses.dataclass(frozen=True)
class StructTypeInfo:
    """Information used to generate constructors for struct types."""

    type: TypeForm
    """The type of the (potential) struct."""
    markers: tuple[Any, ...]
    """Markers from :mod:`tyro.conf` that are associated with this field."""
    default: Any
    """The default value of the struct, or a member of
    :data:`tyro.constructors.MISSING_SINGLETONS` if not present. In a function
    signature, this is `X` in `def main(x=X): ...`. This can be useful for
    populating the default values of the struct."""
    _typevar_context: _resolver.TypeParamAssignmentContext

    @staticmethod
    def make(f: TypeForm | Callable, default: Any) -> StructTypeInfo:
        _, parent_markers = _resolver.unwrap_annotated(f, _markers._Marker)
        f = _resolver.swap_type_using_confstruct(f)
        f, found_subcommand_configs = _resolver.unwrap_annotated(
            f, _confstruct._SubcommandConfig
        )
        if len(found_subcommand_configs) > 0:
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
    from .._fields import is_struct_type

    @registry.struct_rule
    def dataclass_rule(info: StructTypeInfo) -> StructConstructorSpec | None:
        if not dataclasses.is_dataclass(info.type):
            return None

        is_flax_module = False
        try:
            # Check if dataclass is a flax module. This is only possible if flax is already
            # loaded.
            #
            # We generally want to avoid importing flax, since it requires a lot of heavy
            # imports.
            if "flax.linen" in sys.modules.keys():
                import flax.linen

                if issubclass(info.type, flax.linen.Module):
                    is_flax_module = True
        except ImportError:
            pass

        # Handle dataclasses.
        field_list = []
        for dc_field in filter(
            lambda field: field.init, _resolver.resolved_fields(info.type)
        ):
            # For flax modules, we ignore the built-in "name" and "parent" fields.
            if is_flax_module and dc_field.name in ("name", "parent"):
                continue

            default, is_default_from_default_instance = _get_dataclass_field_default(
                dc_field, info.default
            )

            # Try to get helptext from field metadata. This is also intended to be
            # compatible with HuggingFace-style config objects.
            helptext = dc_field.metadata.get("help", None)
            assert isinstance(helptext, (str, type(None)))

            # Try to get helptext from docstrings. This can't be generated
            # dynamically.
            if helptext is None:
                helptext = _docstrings.get_field_docstring(info.type, dc_field.name)

            assert not isinstance(dc_field.type, str)
            field_list.append(
                StructFieldSpec(
                    name=dc_field.name,
                    type=dc_field.type,
                    default=default,
                    is_default_overridden=is_default_from_default_instance,
                    helptext=helptext,
                )
            )
        return StructConstructorSpec(instantiate=info.type, fields=tuple(field_list))

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
        for name, typ in _resolver.get_type_hints_with_backported_syntax(
            cls, include_extras=True
        ).items():
            typ_origin = get_origin(typ)
            is_default_from_default_instance = False
            if valid_default_instance and name in cast(dict, info.default):
                default = cast(dict, info.default)[name]
                is_default_from_default_instance = True
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
                assert (
                    len(args) == 1
                ), "typing.Required[] and typing.NotRequired[T] require a concrete type T."
                typ = args[0]
                del args

            field_list.append(
                StructFieldSpec(
                    name=name,
                    type=typ,
                    default=default,
                    is_default_overridden=is_default_from_default_instance,
                    helptext=_docstrings.get_field_docstring(cls, name),
                )
            )
        return StructConstructorSpec(instantiate=info.type, fields=tuple(field_list))

    @registry.struct_rule
    def attrs_rule(info: StructTypeInfo) -> StructConstructorSpec | None:
        # attr will already be imported if it's used.
        if "attr" not in sys.modules.keys():  # pragma: no cover
            return None

        try:
            import attr
        except ImportError:
            # This is needed for the mock import test in
            # test_missing_optional_packages.py to pass.
            return None

        if not attr.has(info.type):
            return None

        # Resolve forward references in-place, if any exist.
        attr.resolve_types(info.type)

        # Handle attr classes.
        field_list = []
        for attr_field in attr.fields(info.type):
            # Skip fields with init=False.
            if not attr_field.init:
                continue

            # Default handling.
            name = attr_field.name
            default = attr_field.default
            is_default_from_default_instance = False
            if info.default not in MISSING_AND_MISSING_NONPROP:
                if hasattr(info.default, name):
                    default = getattr(info.default, name)
                    is_default_from_default_instance = True
                else:
                    warnings.warn(
                        f"Could not find field {name} in default instance"
                        f" {info.default}, which has"
                        f" type {type(info.default)},",
                        stacklevel=2,
                    )
            elif default is attr.NOTHING:
                default = MISSING_NONPROP
            elif isinstance(default, attr.Factory):  # type: ignore
                default = default.factory()  # type: ignore

            assert attr_field.type is not None, attr_field
            field_list.append(
                StructFieldSpec(
                    name=name,
                    type=attr_field.type,
                    default=default,
                    is_default_overridden=is_default_from_default_instance,
                    helptext=_docstrings.get_field_docstring(info.type, name),
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
                    is_default_overridden=True,
                    helptext=None,
                    _call_argname=k,
                )
            )
        return StructConstructorSpec(instantiate=dict, fields=tuple(field_list))

    @registry.struct_rule
    def namedtuple_rule(info: StructTypeInfo) -> StructConstructorSpec | None:
        if not (
            isinstance(info.type, type)
            and issubclass(info.type, tuple)
            and hasattr(info.type, "_fields")
        ):
            return None

        field_list = []
        field_defaults = getattr(info.type, "_field_defaults", {})

        for name, typ in _resolver.get_type_hints_with_backported_syntax(
            info.type, include_extras=True
        ).items():
            default = field_defaults.get(name, MISSING_NONPROP)
            is_default_from_default_instance = False

            if info.default not in MISSING_AND_MISSING_NONPROP and hasattr(
                info.default, name
            ):
                default = getattr(info.default, name)
                is_default_from_default_instance = True
            elif info.default is MISSING:
                default = MISSING

            field_list.append(
                StructFieldSpec(
                    name=name,
                    type=typ,
                    default=default,
                    is_default_overridden=is_default_from_default_instance,
                    helptext=_docstrings.get_field_docstring(info.type, name),
                )
            )

        return StructConstructorSpec(instantiate=info.type, fields=tuple(field_list))

    @registry.struct_rule
    def sequence_rule(info: StructTypeInfo) -> StructConstructorSpec | None:
        if get_origin(info.type) not in (
            list,
            set,
            tuple,
            Sequence,
            collections.abc.Sequence,
        ) or not isinstance(info.default, Iterable):
            return None

        contained_type = get_args(info.type)[0] if get_args(info.type) else Any

        if all(not is_struct_type(type(x), x) for x in info.default):
            return None

        field_list = []
        for i, default_i in enumerate(info.default):
            field_list.append(
                StructFieldSpec(
                    name=str(i),
                    type=cast(type, contained_type),
                    default=default_i,
                    is_default_overridden=True,
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
                    is_default_overridden=True,
                    helptext="",
                )
            )

        contains_nested = False
        for field in field_list:
            # Inefficient, since is_struct_type will compute StructTypeInfo again.
            field_info = StructTypeInfo.make(field.type, field.default)
            if get_origin(field_info.type) is Union:
                for option in get_args(field_info.type):
                    # The second argument here is the default value, which can help with
                    # narrowing but is generall not necessary.
                    contains_nested |= is_struct_type(option, MISSING_NONPROP)
            contains_nested |= is_struct_type(field.type, field.default)
            if contains_nested:
                break

        if not contains_nested:
            return None
        return StructConstructorSpec(instantiate=tuple, fields=tuple(field_list))

    @registry.struct_rule
    def pydantic_rule(info: StructTypeInfo) -> StructConstructorSpec | None:
        # Check if pydantic is imported
        if "pydantic" not in sys.modules.keys():  # pragma: no cover
            return None

        try:
            import pydantic
        except ImportError:
            # Needed for the mock import test in
            # test_missing_optional_packages.py to pass.
            return None

        try:
            if "pydantic.v1" in sys.modules.keys():
                from pydantic import v1 as pydantic_v1
            else:  # pragma: no cover
                pydantic_v1 = None  # type: ignore
        except ImportError:
            pydantic_v1 = None  # type: ignore

        # Check if the type is a Pydantic model
        try:
            if not (
                issubclass(info.type, pydantic.BaseModel)
                or (
                    pydantic_v1 is not None
                    and issubclass(info.type, pydantic_v1.BaseModel)
                )
            ):
                return None
        except TypeError:
            # issubclass failed!
            return None

        field_list = []
        pydantic_version = int(
            getattr(pydantic, "__version__", "1.0.0").partition(".")[0]
        )

        if pydantic_version < 2 or (
            pydantic_v1 is not None and issubclass(info.type, pydantic_v1.BaseModel)
        ):
            # Pydantic 1.xx
            cls_cast = info.type
            hints = _resolver.get_type_hints_with_backported_syntax(
                info.type, include_extras=True
            )
            for pd1_field in cast(Dict[str, Any], cls_cast.__fields__).values():
                helptext = pd1_field.field_info.description
                if helptext is None:
                    helptext = _docstrings.get_field_docstring(
                        info.type, pd1_field.name
                    )

                default, is_default_from_default_instance = (
                    _get_pydantic_v1_field_default(
                        pd1_field.name, pd1_field, info.default
                    )
                )
                field_list.append(
                    StructFieldSpec(
                        name=pd1_field.name,
                        type=hints[pd1_field.name],
                        default=default,
                        is_default_overridden=is_default_from_default_instance,
                        helptext=helptext,
                    )
                )
        else:
            # Pydantic 2.xx
            for name, pd2_field in cast(Any, info.type).model_fields.items():
                helptext = pd2_field.description
                if helptext is None:
                    helptext = _docstrings.get_field_docstring(info.type, name)

                default, is_default_from_default_instance = (
                    _get_pydantic_v2_field_default(name, pd2_field, info.default)
                )
                field_list.append(
                    StructFieldSpec(
                        name=name,
                        type=(
                            Annotated[  # type: ignore
                                (pd2_field.annotation,) + tuple(pd2_field.metadata)
                            ]
                            if len(pd2_field.metadata) > 0
                            else pd2_field.annotation
                        ),
                        default=default,
                        is_default_overridden=is_default_from_default_instance,
                        helptext=helptext,
                    )
                )

        return StructConstructorSpec(instantiate=info.type, fields=tuple(field_list))


def _ensure_dataclass_instance_used_as_default_is_frozen(
    field: dataclasses.Field, default_instance: Any
) -> None:
    """Ensure that a dataclass type used directly as a default value is marked as
    frozen."""
    assert dataclasses.is_dataclass(default_instance)
    cls = type(default_instance)
    if not cls.__dataclass_params__.frozen:  # type: ignore
        warnings.warn(
            f"Mutable type {cls} is used as a default value for `{field.name}`. This is"
            " dangerous! Consider using `dataclasses.field(default_factory=...)` or"
            f" marking {cls} as frozen."
        )


def _get_dataclass_field_default(
    field: dataclasses.Field, parent_default_instance: Any
) -> tuple[Any, bool]:
    """Helper for getting the default instance for a dataclass field."""
    # If the dataclass's parent is explicitly marked MISSING, mark this field as missing
    # as well.
    if parent_default_instance is MISSING:
        return MISSING, False

    # Try grabbing default from parent instance.
    if (
        parent_default_instance not in MISSING_AND_MISSING_NONPROP
        and parent_default_instance is not None
    ):
        # Populate default from some parent, eg `default=` in `tyro.cli()`.
        if hasattr(parent_default_instance, field.name):
            return getattr(parent_default_instance, field.name), True
        else:
            warnings.warn(
                f"Could not find field {field.name} in default instance"
                f" {parent_default_instance}, which has"
                f" type {type(parent_default_instance)},",
                stacklevel=2,
            )

    # Try grabbing default from dataclass field.
    if (
        field.default not in MISSING_AND_MISSING_NONPROP
        and field.default is not dataclasses.MISSING
    ):
        default = field.default
        # dataclasses.is_dataclass() will also return true for dataclass
        # _types_, not just instances.
        if type(default) is not type and dataclasses.is_dataclass(default):
            _ensure_dataclass_instance_used_as_default_is_frozen(field, default)
        return default, False

    # Populate default from `dataclasses.field(default_factory=...)`.
    if field.default_factory is not dataclasses.MISSING and not (
        # Special case to ignore default_factory if we write:
        # `field: Dataclass = dataclasses.field(default_factory=Dataclass)`.
        #
        # In other words, treat it the same way as: `field: Dataclass`.
        #
        # The only time this matters is when we our dataclass has a `__post_init__`
        # function that mutates the dataclass. We choose here to use the default values
        # before this method is called.
        dataclasses.is_dataclass(field.type) and field.default_factory is field.type
    ):
        return field.default_factory(), False

    # Otherwise, no default.
    return MISSING_NONPROP, False


if TYPE_CHECKING:
    import pydantic as pydantic
    import pydantic.v1.fields as pydantic_v1_fields


def _get_pydantic_v1_field_default(
    name: str,
    field: pydantic_v1_fields.ModelField,
    parent_default_instance: Any,
) -> tuple[Any, bool]:
    """Helper for getting the default instance for a Pydantic field."""

    # Try grabbing default from parent instance.
    if (
        parent_default_instance not in MISSING_AND_MISSING_NONPROP
        and parent_default_instance is not None
    ):
        # Populate default from some parent, eg `default=` in `tyro.cli()`.
        if hasattr(parent_default_instance, name):
            return getattr(parent_default_instance, name), True
        else:
            warnings.warn(
                f"Could not find field {name} in default instance"
                f" {parent_default_instance}, which has"
                f" type {type(parent_default_instance)},",
                stacklevel=2,
            )

    if not field.required:
        return field.get_default(), False

    # Otherwise, no default.
    return MISSING_NONPROP, False


def _get_pydantic_v2_field_default(
    name: str,
    field: pydantic.fields.FieldInfo,
    parent_default_instance: Any,
) -> tuple[Any, bool]:
    """Helper for getting the default instance for a Pydantic field."""

    # Try grabbing default from parent instance.
    if (
        parent_default_instance not in MISSING_AND_MISSING_NONPROP
        and parent_default_instance is not None
    ):
        # Populate default from some parent, eg `default=` in `tyro.cli()`.
        if hasattr(parent_default_instance, name):
            return getattr(parent_default_instance, name), True
        else:
            warnings.warn(
                f"Could not find field {name} in default instance"
                f" {parent_default_instance}, which has"
                f" type {type(parent_default_instance)},",
                stacklevel=2,
            )

    if not field.is_required():
        return field.get_default(call_default_factory=True), False

    # Otherwise, no default.
    return MISSING_NONPROP, False
