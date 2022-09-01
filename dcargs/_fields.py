"""Abstractions for pulling out 'field' definitions, which specify inputs, types, and
defaults, from general callables."""

from __future__ import annotations

import collections
import collections.abc
import dataclasses
import enum
import inspect
import itertools
import typing
import warnings
from typing import Any, Callable, Hashable, Iterable, List, Optional, Type, Union, cast

import docstring_parser
import typing_extensions
from typing_extensions import get_args, get_type_hints, is_typeddict

from . import _docstrings, _instantiators, _resolver, _strings


@dataclasses.dataclass(frozen=True)
class FieldDefinition:
    name: str
    typ: Type
    default: Any
    helptext: Optional[str]
    positional: bool

    # Override the name in our kwargs. Currently only used for dictionary types when
    # the key values aren't strings, but in the future could be used whenever the
    # user-facing argument name doesn't match the keyword expected by our callable.
    name_override: Optional[Any] = None


class _Singleton:
    # Singleton pattern.
    # https://www.python.org/download/releases/2.2/descrintro/#__new__
    def __new__(cls, *args, **kwds):
        it = cls.__dict__.get("__it__")
        if it is not None:
            return it
        cls.__it__ = it = object.__new__(cls)
        it.init(*args, **kwds)
        return it

    def init(self, *args, **kwds):
        pass


class PropagatingMissingType(_Singleton):
    pass


class NonpropagatingMissingType(_Singleton):
    pass


class ExcludeFromCallType(_Singleton):
    pass


# We have two types of missing sentinels: a propagating missing value, which when set as
# a default will set all child values of nested structures as missing as well, and a
# nonpropagating missing sentinel, which does not override child defaults.
MISSING_PROP = PropagatingMissingType()
MISSING_NONPROP = NonpropagatingMissingType()

# When total=False in a TypedDict, we exclude fields from the constructor by default.
EXCLUDE_FROM_CALL = ExcludeFromCallType()

# Note that our "public" missing API will always be the propagating missing sentinel.
MISSING_PUBLIC: Any = MISSING_PROP
"""Sentinel value to mark fields as missing. Can be used to mark fields passed in as a
`default_instance` for `dcargs.cli()` as required."""


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


@dataclasses.dataclass(frozen=True)
class UnsupportedNestedTypeMessage:
    """Reason why a callable cannot be treated as a nested type."""

    message: str


def is_nested_type(typ: Type, default_instance: _DefaultInstance) -> bool:
    """Determine whether a type should be treated as a 'nested type', where a single
    type can be broken down into multiple fields (eg for nested dataclasses or
    classes)."""
    return not isinstance(
        _try_field_list_from_callable(typ, default_instance),
        UnsupportedNestedTypeMessage,
    )


def field_list_from_callable(
    f: Union[Callable, Type],
    default_instance: _DefaultInstance,
) -> List[FieldDefinition]:
    """Generate a list of generic 'field' objects corresponding to the inputs of some
    annotated callable."""
    out = _try_field_list_from_callable(f, default_instance)

    if isinstance(out, UnsupportedNestedTypeMessage):
        raise _instantiators.UnsupportedTypeAnnotationError(out.message)
    return out


# Implementation details below.


_DefaultInstance = Union[
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
    f: Union[Callable, Type],
    default_instance: _DefaultInstance,
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    # Unwrap generics.
    f, type_from_typevar = _resolver.resolve_generic_types(f)
    f = _resolver.narrow_type(f, default_instance)

    # If `f` is a type:
    #     1. Set cls to the type.
    #     2. Consider `f` to be `cls.__init__`.
    cls: Optional[Type] = None
    if isinstance(f, type):
        cls = f
        f = cls.__init__  # type: ignore
        f_origin: Callable = cls
    f_origin = _resolver.unwrap_origin(f)

    # Try special cases.
    if cls is not None and is_typeddict(cls):
        return _try_field_list_from_typeddict(cls, default_instance)

    elif cls is not None and _resolver.is_namedtuple(cls):
        return _try_field_list_from_namedtuple(cls, default_instance)

    elif cls is not None and _resolver.is_dataclass(cls):
        return _try_field_list_from_dataclass(cls, default_instance)

    # Standard container types. These are special because they can be nested structures
    # if they contain other nested types (eg Tuple[Struct, Struct]), or treated as
    # single arguments otherwise (eg Tuple[int, int]).
    #
    # Note that f_origin will be populated if we annotate as `Tuple[..]`, and cls will
    # be populated if we annotated as just `tuple`.
    container_fields = None
    if f_origin is tuple or cls is tuple:
        container_fields = _field_list_from_tuple(f, default_instance)
    elif f_origin in (list, set, typing.Sequence) or cls in (
        list,
        set,
        typing.Sequence,
    ):
        contained_type: Any
        if len(get_args(f)) == 0:
            if default_instance in MISSING_SINGLETONS:
                raise _instantiators.UnsupportedTypeAnnotationError(
                    f"Sequence type {cls} needs either an explicit type or a"
                    " default to infer from."
                )
            assert isinstance(default_instance, Iterable)
        else:
            (contained_type,) = get_args(f)
        f_origin = list if f_origin is typing.Sequence else f_origin  # type: ignore

        container_fields = _try_field_list_from_sequence(
            contained_type, default_instance
        )
    elif f_origin in (collections.abc.Mapping, dict) or cls in (
        collections.abc.Mapping,
        dict,
    ):
        container_fields = _try_field_list_from_dict(f, default_instance)

    # Check if one of the container types matched.
    if container_fields is not None:
        # Found fields!
        if not isinstance(container_fields, UnsupportedNestedTypeMessage):
            return container_fields
        # Got an error,
        else:
            assert isinstance(container_fields, UnsupportedNestedTypeMessage)
            return container_fields

    # General cases.
    if (cls is not None and cls in _known_parsable_types) or _resolver.unwrap_origin(
        f
    ) in _known_parsable_types:
        return UnsupportedNestedTypeMessage(f"{f} should be parsed directly!")
    else:
        return _try_field_list_from_general_callable(f, cls, default_instance)


def _try_field_list_from_typeddict(
    cls: Type, default_instance: _DefaultInstance
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    field_list = []
    valid_default_instance = (
        default_instance not in MISSING_SINGLETONS
        and default_instance is not EXCLUDE_FROM_CALL
    )
    assert not valid_default_instance or isinstance(default_instance, dict)
    for name, typ in get_type_hints(cls).items():
        if valid_default_instance:
            default = default_instance.get(name, MISSING_PROP)  # type: ignore
        elif getattr(cls, "__total__") is False:
            default = EXCLUDE_FROM_CALL
            if is_nested_type(typ, MISSING_NONPROP):
                raise _instantiators.UnsupportedTypeAnnotationError(
                    "`total=False` not supported for nested structures."
                )
        else:
            default = MISSING_PROP

        field_list.append(
            FieldDefinition(
                name=name,
                typ=typ,
                default=default,
                helptext=_docstrings.get_field_docstring(cls, name),
                positional=False,
            )
        )
    return field_list


def _try_field_list_from_namedtuple(
    cls: Type, default_instance: _DefaultInstance
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    # Handle NamedTuples.
    #
    # TODO: in terms of helptext, we currently do display the default NamedTuple
    # helptext. But we (intentionally) don't for dataclasses; this is somewhat
    # inconsistent.
    field_list = []
    field_defaults = getattr(cls, "_field_defaults")

    # Note that _field_types is removed in Python 3.9.
    for name, typ in _resolver.get_type_hints(cls).items():
        # Get default, with priority for `default_instance`.
        default = field_defaults.get(name, MISSING_NONPROP)
        if hasattr(default_instance, name):
            default = getattr(default_instance, name)
        if default_instance is MISSING_PROP:
            default = MISSING_PROP

        field_list.append(
            FieldDefinition(
                name=name,
                typ=typ,
                default=default,
                helptext=_docstrings.get_field_docstring(cls, name),
                positional=False,
            )
        )
    return field_list


def _try_field_list_from_dataclass(
    cls: Type, default_instance: _DefaultInstance
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    # Handle dataclasses.
    field_list = []
    for dc_field in filter(lambda field: field.init, _resolver.resolved_fields(cls)):
        default = _get_dataclass_field_default(dc_field, default_instance)
        field_list.append(
            FieldDefinition(
                name=dc_field.name,
                typ=dc_field.type,
                default=default,
                helptext=_docstrings.get_field_docstring(cls, dc_field.name),
                # Only mark positional if using a dummy field, for taking single types
                # directly as input.
                positional=dc_field.name == _strings.dummy_field_name,
            )
        )
    return field_list


def _field_list_from_tuple(
    f: Union[Callable, Type], default_instance: _DefaultInstance
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    # Fixed-length tuples.
    field_list = []
    children = get_args(f)
    if Ellipsis in children:
        return _try_field_list_from_sequence(
            next(iter(set(children) - {Ellipsis})), default_instance
        )

    # Infer more specific type when tuple annotation isn't subscripted. This generally
    # doesn't happen
    if len(children) == 0:
        if default_instance in MISSING_SINGLETONS:
            raise _instantiators.UnsupportedTypeAnnotationError(
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
            FieldDefinition(
                # Ideally we'd have --tuple[0] instead of --tuple.0 as the command-line
                # argument, but in practice the brackets are annoying because they
                # require escaping.
                name=str(i),
                typ=child,
                default=default_i,
                helptext="",
                # This should really be positional=True, but the CLI is more
                # intuitive for mixed nested/non-nested types in tuples when we
                # stick with kwargs. Tuples are special-cased in _calling.py.
                positional=False,
            )
        )

    contains_nested = False
    for field in field_list:
        contains_nested |= is_nested_type(field.typ, field.default)
    if not contains_nested:
        # We could also check for variable length children, which can be populated when
        # the tuple is interpreted as a nested field but not a directly parsed one.
        return UnsupportedNestedTypeMessage(
            "Tuple does not contain any nested structures."
        )

    return field_list


def _try_field_list_from_sequence(
    contained_type: Type,
    default_instance: _DefaultInstance,
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
            FieldDefinition(
                name=str(i),
                typ=contained_type,
                default=default_i,
                helptext="",
                positional=False,
            )
        )
    return field_list


def _try_field_list_from_dict(
    f: Union[Callable, Type],
    default_instance: _DefaultInstance,
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    if default_instance in MISSING_SINGLETONS:
        return UnsupportedNestedTypeMessage(
            "Nested dictionary structures must have a default instance specified."
        )
    field_list = []
    for k, v in cast(dict, default_instance).items():
        field_list.append(
            FieldDefinition(
                name=str(k) if not isinstance(k, enum.Enum) else k.name,
                typ=type(v),
                default=v,
                helptext=None,
                positional=False,
                # Dictionary specific key:
                name_override=k,
            )
        )
    return field_list


def _try_field_list_from_general_callable(
    f: Union[Callable, Type],
    cls: Optional[Type],
    default_instance: _DefaultInstance,
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    # Handle general callables.
    if default_instance not in MISSING_SINGLETONS:
        return UnsupportedNestedTypeMessage(
            "`default_instance` is supported only for select types:"
            " dataclasses, lists, NamedTuple, TypedDict, etc."
        )

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
    if not isinstance(out, UnsupportedNestedTypeMessage):
        return out

    # Return error message.
    assert isinstance(out, UnsupportedNestedTypeMessage)
    return out


def _field_list_from_params(
    f: Union[Callable, Type], cls: Optional[Type], params: List[inspect.Parameter]
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    # Get type annotations, docstrings.
    docstring = inspect.getdoc(f)
    docstring_from_arg_name = {}
    if docstring is not None:
        for param_doc in docstring_parser.parse(docstring).params:
            docstring_from_arg_name[param_doc.arg_name] = param_doc.description
    del docstring

    # This will throw a type error for torch.device, typing.Dict, etc.
    try:
        hints = get_type_hints(f)
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

        field_list.append(
            FieldDefinition(
                name=param.name,
                # Note that param.annotation does not resolve forward references.
                typ=hints[param.name],
                default=default,
                helptext=helptext,
                positional=param.kind is inspect.Parameter.POSITIONAL_ONLY,
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
        # Populate default from some parent, eg `default_instance` in `dcargs.cli()`.
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
