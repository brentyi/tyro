"""Abstractions for pulling out 'field' definitions, which specify inputs, types, and
defaults, from general callables."""
from __future__ import annotations

import collections
import collections.abc
import dataclasses
import enum
import functools
import inspect
import itertools
import numbers
import os
import sys
import typing
import warnings
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Hashable,
    Iterable,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
    cast,
)

import docstring_parser
import typing_extensions
from typing_extensions import (
    NotRequired,
    Required,
    get_args,
    get_origin,
    get_type_hints,
    is_typeddict,
)

from . import conf  # Avoid circular import.
from . import (
    _docstrings,
    _instantiators,
    _resolver,
    _singleton,
    _strings,
    _unsafe_cache,
)
from ._typing import TypeForm
from .conf import _confstruct, _markers


@dataclasses.dataclass(frozen=True)
class FieldDefinition:
    name: str
    type_or_callable: Union[TypeForm[Any], Callable]
    """Type or callable for this field. This should have all Annotated[] annotations
    stripped."""
    default: Any
    helptext: Optional[str]
    markers: FrozenSet[_markers._Marker]
    custom_constructor: bool

    argconf: _confstruct._ArgConfiguration

    # Override the name in our kwargs. Useful whenever the user-facing argument name
    # doesn't match the keyword expected by our callable.
    call_argname: Any

    def __post_init__(self):
        if (
            _markers.Fixed in self.markers or _markers.Suppress in self.markers
        ) and self.default in MISSING_SINGLETONS:
            raise _instantiators.UnsupportedTypeAnnotationError(
                f"Field {self.name} is missing a default value!"
            )

    @staticmethod
    def make(
        name: str,
        type_or_callable: Union[TypeForm[Any], Callable],
        default: Any,
        helptext: Optional[str],
        call_argname_override: Optional[Any] = None,
        *,
        markers: Tuple[_markers._Marker, ...] = (),
    ):
        # Try to extract argconf overrides from type.
        _, argconfs = _resolver.unwrap_annotated(
            type_or_callable, _confstruct._ArgConfiguration
        )
        argconf = _confstruct._ArgConfiguration(
            None,
            None,
            help=None,
            aliases=None,
            prefix_name=True,
            constructor_factory=None,
        )
        for overwrite_argconf in argconfs:
            # Apply any annotated argument configuration values.
            argconf = dataclasses.replace(
                argconf,
                **{
                    field.name: getattr(overwrite_argconf, field.name)
                    for field in dataclasses.fields(overwrite_argconf)
                    if getattr(overwrite_argconf, field.name) is not None
                },
            )
            if argconf.help is not None:
                helptext = argconf.help

        type_or_callable, inferred_markers = _resolver.unwrap_annotated(
            type_or_callable, _markers._Marker
        )
        return FieldDefinition(
            name if argconf.name is None else argconf.name,
            type_or_callable
            if argconf.constructor_factory is None
            else argconf.constructor_factory(),
            default,
            helptext,
            markers=frozenset(inferred_markers).union(markers),
            custom_constructor=argconf.constructor_factory is not None,
            argconf=argconf,
            call_argname=call_argname_override
            if call_argname_override is not None
            else name,
        )

    def add_markers(self, markers: Tuple[Any, ...]) -> FieldDefinition:
        return dataclasses.replace(
            self,
            markers=self.markers.union(markers),
        )

    def is_positional(self) -> bool:
        """Returns True if the argument should be positional in the commandline."""
        return (
            # Explicit positionals.
            _markers.Positional in self.markers
            # Dummy dataclasses should have a single positional field.
            or self.name == _strings.dummy_field_name
            or (
                # Make required arguments positional.
                _markers.PositionalRequiredArgs in self.markers
                and self.default in MISSING_SINGLETONS
            )
        )

    def is_positional_call(self) -> bool:
        """Returns True if the argument should be positional in underlying Python call."""
        return (
            # Explicit positionals.
            _markers._PositionalCall in self.markers
            # Dummy dataclasses should have a single positional field.
            or self.name == _strings.dummy_field_name
        )


class PropagatingMissingType(_singleton.Singleton):
    pass


class NonpropagatingMissingType(_singleton.Singleton):
    pass


class ExcludeFromCallType(_singleton.Singleton):
    pass


class NotRequiredButWeDontKnowTheValueType(_singleton.Singleton):
    pass


# We have two types of missing sentinels: a propagating missing value, which when set as
# a default will set all child values of nested structures as missing as well, and a
# nonpropagating missing sentinel, which does not override child defaults.
MISSING_PROP = PropagatingMissingType()
MISSING_NONPROP = NonpropagatingMissingType()

# When total=False in a TypedDict, we exclude fields from the constructor by default.
NOT_REQUIRED_BUT_WE_DONT_KNOW_THE_VALUE = NotRequiredButWeDontKnowTheValueType()


EXCLUDE_FROM_CALL = ExcludeFromCallType()

# Note that our "public" missing API will always be the propagating missing sentinel.
MISSING: Any = MISSING_PROP
"""Sentinel value to mark fields as missing. Can be used to mark fields passed in as a
`default_instance` for `tyro.cli()` as required."""


MISSING_SINGLETONS = [
    dataclasses.MISSING,
    MISSING_PROP,
    MISSING_NONPROP,
    inspect.Parameter.empty,
]
try:
    # Undocumented feature: support omegaconf dataclasses out of the box.
    import omegaconf

    MISSING_SINGLETONS.append(omegaconf.MISSING)
except ImportError:
    pass

DEFAULT_SENTINEL_SINGLETONS = MISSING_SINGLETONS + [
    NOT_REQUIRED_BUT_WE_DONT_KNOW_THE_VALUE,
    EXCLUDE_FROM_CALL,
]


@dataclasses.dataclass(frozen=True)
class UnsupportedNestedTypeMessage:
    """Reason why a callable cannot be treated as a nested type."""

    message: str


@_unsafe_cache.unsafe_cache(maxsize=1024)
def is_nested_type(
    typ: Union[TypeForm[Any], Callable], default_instance: DefaultInstance
) -> bool:
    """Determine whether a type should be treated as a 'nested type', where a single
    type can be broken down into multiple fields (eg for nested dataclasses or
    classes).

    TODO: we should come up with a better name than 'nested type', which is a little bit
    misleading."""
    return not isinstance(
        _try_field_list_from_callable(typ, default_instance),
        UnsupportedNestedTypeMessage,
    )


def field_list_from_callable(
    f: Union[Callable, TypeForm[Any]],
    default_instance: DefaultInstance,
) -> Tuple[
    Union[Callable, TypeForm[Any]], Dict[TypeVar, TypeForm], List[FieldDefinition]
]:
    """Generate a list of generic 'field' objects corresponding to the inputs of some
    annotated callable.

    Returns:
        The type that `f` is resolved as.
        A type_from_typevar dict.
        A list of field definitions.
    """
    # Resolve generic types.
    f, type_from_typevar = _resolver.resolve_generic_types(f)
    f = _resolver.narrow_type(f, default_instance)

    # Try to generate field list.
    field_list = _try_field_list_from_callable(f, default_instance)

    if isinstance(field_list, UnsupportedNestedTypeMessage):
        raise _instantiators.UnsupportedTypeAnnotationError(field_list.message)

    # Recursively apply markers.
    _, parent_markers = _resolver.unwrap_annotated(f, _markers._Marker)
    field_list = list(map(lambda field: field.add_markers(parent_markers), field_list))

    # Try to resolve types in our list of fields.
    def resolve(field: FieldDefinition) -> FieldDefinition:
        typ = field.type_or_callable
        typ = _resolver.apply_type_from_typevar(typ, type_from_typevar)
        typ = _resolver.type_from_typevar_constraints(typ)
        typ = _resolver.narrow_container_types(typ, field.default)
        typ = _resolver.narrow_union_type(typ, field.default)

        # Check that the default value matches the final resolved type.
        try:
            if (
                type(typ) is type
                and not isinstance(field.default, typ)  # type: ignore
                # If a custom constructor is set, field.type_or_callable may not be
                # matched to the annotated type.
                and not field.custom_constructor
                and field.default not in DEFAULT_SENTINEL_SINGLETONS
                # The numeric tower in Python is wacky. This logic is non-critical, so
                # we'll just skip it (+the complexity) for numbers.
                and not isinstance(field.default, numbers.Number)
            ):
                # If the default value doesn't match the resolved type, we expand the
                # type. This is inspired by https://github.com/brentyi/tyro/issues/88.
                warnings.warn(
                    f"The field {field.name} is annotated with type {field.type_or_callable}, "
                    f"but the default value {field.default} has type {type(field.default)}. "
                    f"We'll try to handle this gracefully, but it may cause unexpected behavior."
                )
                typ = Union[typ, type(field.default)]  # type: ignore
        except TypeError:
            # An isinstance() check wasn't possible.
            pass

        field = dataclasses.replace(field, type_or_callable=typ)
        return field

    field_list = list(map(resolve, field_list))

    return f, type_from_typevar, field_list


# Implementation details below.


DefaultInstance = Union[
    Any, PropagatingMissingType, NonpropagatingMissingType, ExcludeFromCallType
]

_known_parsable_types = set(
    filter(
        lambda x: isinstance(x, Hashable),  # type: ignore
        itertools.chain(
            __builtins__.values(),  # type: ignore
            vars(typing).values(),
            vars(typing_extensions).values(),
            vars(collections.abc).values(),
        ),
    )
)


def _try_field_list_from_callable(
    f: Union[Callable, TypeForm[Any]],
    default_instance: DefaultInstance,
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    f, found_subcommand_configs = _resolver.unwrap_annotated(
        f, conf._confstruct._SubcommandConfiguration
    )
    if len(found_subcommand_configs) > 0:
        default_instance = found_subcommand_configs[0].default

    # Unwrap generics.
    f, _ = _resolver.resolve_generic_types(f)
    f = _resolver.narrow_type(f, default_instance)
    f_origin = _resolver.unwrap_origin_strip_extras(cast(TypeForm, f))

    # If `f` is a type:
    #     1. Set cls to the type.
    #     2. Consider `f` to be `cls.__init__`.
    cls: Optional[TypeForm[Any]] = None
    if inspect.isclass(f):
        cls = f
        if hasattr(cls, "__init__") and cls.__init__ is not object.__init__:
            f = cls.__init__  # type: ignore
        elif hasattr(cls, "__new__") and cls.__new__ is not object.__new__:
            f = cls.__new__
        else:
            return UnsupportedNestedTypeMessage(
                f"Cannot instantiate class {cls} with no unique __init__ or __new__"
                " method."
            )
        f_origin = cls  # type: ignore

    # Try field generation from class inputs.
    if cls is not None:
        for match, field_list_from_class in (
            (is_typeddict, _field_list_from_typeddict),
            (_resolver.is_namedtuple, _field_list_from_namedtuple),
            (_resolver.is_dataclass, _field_list_from_dataclass),
            (_is_attrs, _field_list_from_attrs),
            (_is_pydantic, _field_list_from_pydantic),
        ):
            if match(cls):
                return field_list_from_class(cls, default_instance)

    # Standard container types. These are different because they can be nested structures
    # if they contain other nested types (eg Tuple[Struct, Struct]), or treated as
    # single arguments otherwise (eg Tuple[int, int]).
    #
    # Note that f_origin will be populated if we annotate as `Tuple[..]`, and cls will
    # be populated if we annotate as just `tuple`.
    if f_origin is tuple or cls is tuple:
        return _field_list_from_tuple(f, default_instance)
    elif f_origin in (collections.abc.Mapping, dict) or cls in (
        collections.abc.Mapping,
        dict,
    ):
        return _field_list_from_dict(f, default_instance)
    elif f_origin in (list, set, typing.Sequence) or cls in (
        list,
        set,
        typing.Sequence,
    ):
        return _field_list_from_sequence_checked(f, default_instance)

    # General cases.
    if (
        cls is not None and cls in _known_parsable_types
    ) or _resolver.unwrap_origin_strip_extras(f) in _known_parsable_types:
        return UnsupportedNestedTypeMessage(f"{f} should be parsed directly!")
    elif (
        cls is not None
        and issubclass(_resolver.unwrap_origin_strip_extras(cls), os.PathLike)
        and _instantiators.is_type_string_converter(cls)
    ):
        return UnsupportedNestedTypeMessage(
            f"PathLike {cls} should be parsed directly!"
        )
    else:
        return _try_field_list_from_general_callable(f, cls, default_instance)


def _field_list_from_typeddict(
    cls: TypeForm[Any], default_instance: DefaultInstance
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    field_list = []
    valid_default_instance = (
        default_instance not in MISSING_SINGLETONS
        and default_instance is not EXCLUDE_FROM_CALL
    )
    assert not valid_default_instance or isinstance(default_instance, dict)
    total = getattr(cls, "__total__", True)
    assert isinstance(total, bool)
    assert not valid_default_instance or isinstance(default_instance, dict)
    for name, typ in get_type_hints(cls, include_extras=True).items():
        typ_origin = get_origin(typ)
        if valid_default_instance and name in cast(dict, default_instance):
            default = cast(dict, default_instance)[name]
        elif typ_origin is Required and total is False:
            # Support total=False.
            default = MISSING_PROP
        elif total is False:
            # Support total=False.
            default = EXCLUDE_FROM_CALL
            if is_nested_type(typ, MISSING_NONPROP):
                # total=False behavior is unideal for nested structures.
                pass
                # raise _instantiators.UnsupportedTypeAnnotationError(
                #     "`total=False` not supported for nested structures."
                # )
        elif typ_origin is NotRequired:
            # Support typing.NotRequired[].
            default = EXCLUDE_FROM_CALL
        else:
            default = MISSING_PROP

        # Nested types need to be populated / can't be excluded from the call.
        if default is EXCLUDE_FROM_CALL and is_nested_type(typ, MISSING_NONPROP):
            default = MISSING_NONPROP

        if typ_origin in (Required, NotRequired):
            args = get_args(typ)
            assert (
                len(args) == 1
            ), "typing.Required[] and typing.NotRequired[T] require a concrete type T."
            typ = args[0]
            del args

        field_list.append(
            FieldDefinition.make(
                name=name,
                type_or_callable=typ,
                default=default,
                helptext=_docstrings.get_field_docstring(cls, name),
            )
        )
    return field_list


def _field_list_from_namedtuple(
    cls: TypeForm[Any], default_instance: DefaultInstance
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    # Handle NamedTuples.
    #
    # TODO: in terms of helptext, we currently do display the default NamedTuple
    # helptext. But we (intentionally) don't for dataclasses; this is somewhat
    # inconsistent.
    field_list = []
    field_defaults = getattr(cls, "_field_defaults")

    # Note that _field_types is removed in Python 3.9.
    for name, typ in get_type_hints(cls, include_extras=True).items():
        # Get default, with priority for `default_instance`.
        default = field_defaults.get(name, MISSING_NONPROP)
        if hasattr(default_instance, name):
            default = getattr(default_instance, name)
        if default_instance is MISSING_PROP:
            default = MISSING_PROP

        field_list.append(
            FieldDefinition.make(
                name=name,
                type_or_callable=typ,
                default=default,
                helptext=_docstrings.get_field_docstring(cls, name),
            )
        )
    return field_list


def _field_list_from_dataclass(
    cls: TypeForm[Any], default_instance: DefaultInstance
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    is_flax_module = False
    try:
        # Check if dataclass is a flax module. This is only possible if flax is already
        # loaded.
        #
        # We generally want to avoid importing flax, since it requires a lot of heavy
        # imports.
        if "flax.linen" in sys.modules.keys():
            import flax.linen

            if issubclass(cls, flax.linen.Module):
                is_flax_module = True
    except ImportError:
        pass

    # Handle dataclasses.
    field_list = []
    for dc_field in filter(lambda field: field.init, _resolver.resolved_fields(cls)):
        # For flax modules, we ignore the built-in "name" and "parent" fields.
        if is_flax_module and dc_field.name in ("name", "parent"):
            continue

        default = _get_dataclass_field_default(dc_field, default_instance)

        # Try to get helptext from field metadata. This is also intended to be
        # compatible with HuggingFace-style config objects.
        helptext = dc_field.metadata.get("help", None)
        assert isinstance(helptext, (str, type(None)))

        # Try to get helptext from docstrings. Note that this can't be generated
        # dynamically.
        if helptext is None:
            helptext = _docstrings.get_field_docstring(cls, dc_field.name)

        field_list.append(
            FieldDefinition.make(
                name=dc_field.name,
                type_or_callable=dc_field.type,
                default=default,
                helptext=helptext,
            )
        )
    return field_list


# Support attrs and pydantic if they're installed.

try:
    import pydantic
except ImportError:
    pydantic = None  # type: ignore


def _is_pydantic(cls: TypeForm[Any]) -> bool:
    return pydantic is not None and issubclass(cls, pydantic.BaseModel)


def _field_list_from_pydantic(
    cls: TypeForm[Any], default_instance: DefaultInstance
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    assert pydantic is not None

    # Handle pydantic models.
    field_list = []
    pydantic_version = int(getattr(pydantic, "__version__", "1.0.0").partition(".")[0])
    if pydantic_version < 2:  # pragma: no cover
        # Pydantic 1.xx.
        for pd_field in cls.__fields__.values():  # type: ignore
            helptext = pd_field.field_info.description
            if helptext is None:
                helptext = _docstrings.get_field_docstring(cls, pd_field.name)

            field_list.append(
                FieldDefinition.make(
                    name=pd_field.name,
                    type_or_callable=pd_field.outer_type_,
                    default=(
                        MISSING_NONPROP if pd_field.required else pd_field.get_default()
                    ),
                    helptext=helptext,
                )
            )
    else:
        # Pydantic 2.xx.
        for name, pd_field in cls.model_fields.items():  # type: ignore
            helptext = pd_field.description
            if helptext is None:
                helptext = _docstrings.get_field_docstring(cls, name)

            field_list.append(
                FieldDefinition.make(
                    name=name,
                    type_or_callable=pd_field.annotation,
                    markers=tuple(
                        meta
                        for meta in pd_field.metadata
                        if isinstance(meta, _markers._Marker)
                    ),
                    default=(
                        MISSING_NONPROP
                        if pd_field.is_required()
                        else pd_field.get_default(call_default_factory=True)
                    ),
                    helptext=helptext,
                )
            )
    return field_list


try:
    import attr
except ImportError:
    attr = None  # type: ignore


def _is_attrs(cls: TypeForm[Any]) -> bool:
    return attr is not None and attr.has(cls)


def _field_list_from_attrs(
    cls: TypeForm[Any], default_instance: DefaultInstance
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    assert attr is not None

    # Handle attr classes.
    field_list = []
    for attr_field in attr.fields(cls):
        # Default handling.
        default = attr_field.default
        if default is attr.NOTHING:
            default = MISSING_NONPROP
        elif isinstance(default, attr.Factory):  # type: ignore
            default = default.factory()  # type: ignore

        assert attr_field.type is not None
        field_list.append(
            FieldDefinition.make(
                name=attr_field.name,
                type_or_callable=attr_field.type,
                default=default,
                helptext=_docstrings.get_field_docstring(cls, attr_field.name),
            )
        )
    return field_list


def _field_list_from_tuple(
    f: Union[Callable, TypeForm[Any]], default_instance: DefaultInstance
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    # Fixed-length tuples.
    field_list: List[FieldDefinition] = []
    children = get_args(f)
    if Ellipsis in children:
        return _try_field_list_from_sequence_inner(
            next(iter(set(children) - {Ellipsis})), default_instance
        )

    # Infer more specific type when tuple annotation isn't subscripted. This generally
    # doesn't happen
    if len(children) == 0:
        if default_instance in MISSING_SINGLETONS:
            return UnsupportedNestedTypeMessage(
                "If contained types of a tuple are not specified in the annotation, a"
                " default instance must be specified."
            )
        else:
            assert isinstance(default_instance, tuple)
            children = tuple(type(x) for x in default_instance)

    if (
        default_instance in MISSING_SINGLETONS
        # EXCLUDE_FROM_CALL indicates we're inside a TypedDict, with total=False.
        or default_instance is EXCLUDE_FROM_CALL
    ):
        default_instance = (default_instance,) * len(children)

    for i, child in enumerate(children):
        default_i = default_instance[i]  # type: ignore
        field_list.append(
            FieldDefinition.make(
                # Ideally we'd have --tuple[0] instead of --tuple.0 as the command-line
                # argument, but in practice the brackets are annoying because they
                # require escaping.
                name=str(i),
                type_or_callable=child,
                default=default_i,
                helptext="",
                # This should really set the positional marker, but the CLI is more
                # intuitive for mixed nested/non-nested types in tuples when we stick
                # with kwargs. Tuples are special-cased in _calling.py.
            )
        )

    contains_nested = False
    for field in field_list:
        contains_nested |= is_nested_type(field.type_or_callable, field.default)
    if not contains_nested:
        # We could also check for variable length children, which can be populated when
        # the tuple is interpreted as a nested field but not a directly parsed one.
        return UnsupportedNestedTypeMessage(
            "Tuple does not contain any nested structures."
        )

    return field_list


def _field_list_from_sequence_checked(
    f: Union[Callable, TypeForm[Any]], default_instance: DefaultInstance
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    contained_type: Any
    if len(get_args(f)) == 0:
        if default_instance in MISSING_SINGLETONS:
            return UnsupportedNestedTypeMessage(
                f"Sequence type {f} needs either an explicit type or a"
                " default to infer from."
            )
        assert isinstance(default_instance, Iterable)
        contained_type = next(iter(default_instance))
    else:
        (contained_type,) = get_args(f)
    return _try_field_list_from_sequence_inner(contained_type, default_instance)


def _try_field_list_from_sequence_inner(
    contained_type: TypeForm[Any],
    default_instance: DefaultInstance,
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    # When no default instance is specified:
    #     If we have List[int] => this can be parsed as a single field.
    #     If we have List[SomeStruct] => OK.
    if default_instance in MISSING_SINGLETONS and not is_nested_type(
        contained_type, MISSING_NONPROP
    ):
        return UnsupportedNestedTypeMessage(
            f"Sequence containing type {contained_type} should be parsed directly!"
        )

    # If we have a default instance:
    #     [int, int, int] => this can be parsed as a single field.
    #     [SomeStruct, int, int] => OK.
    if isinstance(default_instance, Iterable) and all(
        [not is_nested_type(type(x), x) for x in default_instance]
    ):
        return UnsupportedNestedTypeMessage(
            f"Sequence with default {default_instance} should be parsed directly!"
        )
    if default_instance in MISSING_SINGLETONS:
        # We use the broader error type to prevent it from being caught by
        # is_possibly_nested_type(). This is for sure a bad annotation!
        raise _instantiators.UnsupportedTypeAnnotationError(
            "For variable-length sequences over nested types, we need a default value"
            " to infer length from."
        )

    field_list = []
    for i, default_i in enumerate(default_instance):  # type: ignore
        field_list.append(
            FieldDefinition.make(
                name=str(i),
                type_or_callable=contained_type,
                default=default_i,
                helptext="",
            )
        )
    return field_list


def _field_list_from_dict(
    f: Union[Callable, TypeForm[Any]],
    default_instance: DefaultInstance,
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    if default_instance in MISSING_SINGLETONS or len(cast(dict, default_instance)) == 0:
        return UnsupportedNestedTypeMessage(
            "Nested dictionary structures must have non-empty default instance specified."
        )
    field_list = []
    for k, v in cast(dict, default_instance).items():
        field_list.append(
            FieldDefinition.make(
                name=str(k) if not isinstance(k, enum.Enum) else k.name,
                type_or_callable=type(v),
                default=v,
                helptext=None,
                # Dictionary specific key:
                call_argname_override=k,
            )
        )
    return field_list


def _try_field_list_from_general_callable(
    f: Union[Callable, TypeForm[Any]],
    cls: Optional[TypeForm[Any]],
    default_instance: DefaultInstance,
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    # Generate field list from function signature.
    if not callable(f):
        return UnsupportedNestedTypeMessage(
            f"Cannot extract annotations from {f}, which is not a callable type."
        )
    params = list(inspect.signature(f).parameters.values())
    if cls is not None:
        # Ignore self parameter.
        params = params[1:]

    out = _field_list_from_params(f, cls, params)
    if isinstance(out, UnsupportedNestedTypeMessage):
        # Return error message.
        return out

    # If a default is provided: .
    if default_instance not in MISSING_SINGLETONS:
        for i, field in enumerate(out):
            out[i] = field.add_markers((_markers._OPTIONAL_GROUP,))

    return out


def _field_list_from_params(
    f: Union[Callable, TypeForm[Any]],
    cls: Optional[TypeForm[Any]],
    params: List[inspect.Parameter],
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    # Unwrap functools.wraps and functools.partial.
    done = False
    while not done:
        done = True
        if hasattr(f, "__wrapped__"):
            f = f.__wrapped__
            done = False
        if isinstance(f, functools.partial):
            f = f.func
            done = False

    # Sometime functools.* is applied to a class.
    if inspect.isclass(f):
        cls = f
        f = f.__init__  # type: ignore

    # Get type annotations, docstrings.
    docstring = inspect.getdoc(f)
    docstring_from_arg_name = {}
    if docstring is not None:
        for param_doc in docstring_parser.parse(docstring).params:
            docstring_from_arg_name[param_doc.arg_name] = param_doc.description
    del docstring

    # This will throw a type error for torch.device, typing.Dict, etc.
    try:
        hints = get_type_hints(f, include_extras=True)
    except TypeError:
        return UnsupportedNestedTypeMessage(f"Could not get hints for {f}!")

    field_list = []
    for param in params:
        # Get default value.
        default = param.default

        # Get helptext from docstring.
        helptext = docstring_from_arg_name.get(param.name)
        if helptext is None and cls is not None:
            helptext = _docstrings.get_field_docstring(cls, param.name)

        if param.name not in hints:
            out = UnsupportedNestedTypeMessage(
                f"Expected fully type-annotated callable, but {f} with arguments"
                f" {tuple(map(lambda p: p.name, params))} has no annotation for"
                f" '{param.name}'."
            )
            if param.kind is param.KEYWORD_ONLY:
                # If keyword only: this can't possibly be an instantiator function
                # either, so we escalate to an error.
                raise _instantiators.UnsupportedTypeAnnotationError(out.message)
            return out

        # Set markers for positional + variadic arguments.
        markers: Tuple[Any, ...] = ()
        typ: Any = hints[param.name]
        if param.kind is inspect.Parameter.POSITIONAL_ONLY:
            markers = (_markers.Positional, _markers._PositionalCall)
        elif param.kind is inspect.Parameter.VAR_POSITIONAL:
            # Handle *args signatures.
            #
            # This will create a `--args T [T ...]` CLI argument.
            markers = (_markers._UnpackArgsCall,)
            typ = Tuple.__getitem__((typ, ...))  # type: ignore
            default = ()
        elif param.kind is inspect.Parameter.VAR_KEYWORD:
            # Handle *kwargs signatures.
            #
            # This will create a `--kwargs STR T [STR T ...]` CLI argument.
            #
            # Note that it would be straightforward to make both this and *args truly
            # positional, omitting the --args/--kwargs prefix, but we are choosing not
            # to because it would make *args and **kwargs difficult to use in
            # conjunction.
            markers = (_markers._UnpackKwargsCall,)
            typ = Dict.__getitem__((str, typ))  # type: ignore
            default = {}

        field_list.append(
            FieldDefinition.make(
                name=param.name,
                # Note that param.annotation doesn't resolve forward references.
                type_or_callable=typ,
                default=default,
                helptext=helptext,
                markers=markers,
            )
        )

    return field_list


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
) -> Optional[Any]:
    """Helper for getting the default instance for a field."""
    # If the dataclass's parent is explicitly marked MISSING, mark this field as missing
    # as well.
    if parent_default_instance is MISSING_PROP:
        return MISSING_PROP

    # Try grabbing default from parent instance.
    if (
        parent_default_instance not in MISSING_SINGLETONS
        and parent_default_instance is not None
    ):
        # Populate default from some parent, eg `default_instance` in `tyro.cli()`.
        if hasattr(parent_default_instance, field.name):
            return getattr(parent_default_instance, field.name)
        else:
            warnings.warn(
                f"Could not find field {field.name} in default instance"
                f" {parent_default_instance}, which has"
                f" type {type(parent_default_instance)},",
                stacklevel=2,
            )

    # Try grabbing default from dataclass field.
    if field.default not in MISSING_SINGLETONS:
        default = field.default
        # Note that dataclasses.is_dataclass() will also return true for dataclass
        # _types_, not just instances.
        if type(default) is not type and dataclasses.is_dataclass(default):
            _ensure_dataclass_instance_used_as_default_is_frozen(field, default)
        return default

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
        dataclasses.is_dataclass(field.type)
        and field.default_factory is field.type
    ):
        return field.default_factory()

    # Otherwise, no default. This is different from MISSING, because MISSING propagates
    # to children. We could revisit this design to make it clearer.
    return MISSING_NONPROP
