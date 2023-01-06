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
from attr import dataclass
from typing_extensions import Annotated, get_args, get_type_hints, is_typeddict

from . import conf  # Avoid circular import.
from . import _docstrings, _instantiators, _resolver, _singleton, _strings
from ._typing import TypeForm
from .conf import _confstruct, _markers
from .registry import _registry


@dataclasses.dataclass(frozen=True)
class FieldDefinition:
    name: str
    typ: TypeForm[Any]
    default: Any
    helptext: Optional[str]
    markers: FrozenSet[_markers._Marker]

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
        typ: TypeForm[Any],
        default: Any,
        helptext: Optional[str],
        call_argname_override: Optional[Any] = None,
        *,
        markers: Tuple[_markers._Marker, ...] = (),
    ):
        # Try to extract argconf overrides from type.
        _, argconfs = _resolver.unwrap_annotated(typ, _confstruct._ArgConfiguration)
        if len(argconfs) == 0:
            argconf = _confstruct._ArgConfiguration(None, None, None)
        else:
            assert len(argconfs) == 1
            (argconf,) = argconfs
            helptext = argconf.help

        typ, inferred_markers = _resolver.unwrap_annotated(typ, _markers._Marker)
        return FieldDefinition(
            name if argconf.name is None else argconf.name,
            typ,
            default,
            helptext,
            frozenset(inferred_markers).union(markers),
            argconf,
            call_argname_override if call_argname_override is not None else name,
        )

    def add_markers(self, markers: Tuple[_markers._Marker, ...]) -> FieldDefinition:
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


# We have two types of missing sentinels: a propagating missing value, which when set as
# a default will set all child values of nested structures as missing as well, and a
# nonpropagating missing sentinel, which does not override child defaults.
MISSING_PROP = PropagatingMissingType()
MISSING_NONPROP = NonpropagatingMissingType()

# When total=False in a TypedDict, we exclude fields from the constructor by default.
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


@dataclasses.dataclass(frozen=True)
class UnsupportedNestedTypeMessage:
    """Reason why a callable cannot be treated as a nested type."""

    message: str


_DefaultInstance = Union[
    Any, PropagatingMissingType, NonpropagatingMissingType, ExcludeFromCallType
]


def is_nested_type(typ: TypeForm[Any], default_instance: _DefaultInstance) -> bool:
    """Determine whether a type should be treated as a 'nested type', where a single
    type can be broken down into multiple fields (eg for nested dataclasses or
    classes).

    TODO: we should come up with a better name than 'nested type', which is a little bit
    misleading."""
    try:
        field_list_from_callable(typ, default_instance)
    except _instantiators.UnsupportedTypeAnnotationError:
        return False
    return True


def field_list_from_callable(
    f: Union[Callable, TypeForm[Any]],
    default_instance: _DefaultInstance,
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
    f, parent_markers = _resolver.unwrap_annotated(f, _markers._Marker)
    f = _registry.get_constructor_for_type(f, default_instance)
    # field_list = _try_field_list_from_callable(f, default_instance)
    field_list = _field_list_from_callable_signature(f)

    if isinstance(field_list, UnsupportedNestedTypeMessage):
        raise _instantiators.UnsupportedTypeAnnotationError(field_list.message)

    # Recursively apply markers.
    field_list = list(map(lambda field: field.add_markers(parent_markers), field_list))

    # Try to resolve types in our list of fields.
    def resolve(field: FieldDefinition) -> FieldDefinition:
        typ = field.typ
        typ = _resolver.apply_type_from_typevar(typ, type_from_typevar)
        typ = _resolver.type_from_typevar_constraints(typ)
        typ = _resolver.narrow_container_types(typ, field.default)
        typ = _resolver.narrow_union_type(typ, field.default)
        typ = _registry.get_constructor_for_type(typ, field.default)
        field = dataclasses.replace(field, typ=typ)
        return field

    field_list = list(map(resolve, field_list))

    return f, type_from_typevar, field_list


# Implementation details below.

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


def _field_list_from_callable_signature(
    f: Union[Callable, TypeForm[Any]]
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    if (f in _known_parsable_types) or _resolver.unwrap_origin_strip_extras(
        f
    ) in _known_parsable_types:
        return UnsupportedNestedTypeMessage(f"{f} should be parsed directly!")

    # Generate field list from function signature.
    if not callable(f):
        return UnsupportedNestedTypeMessage(
            f"Cannot extract annotations from {f}, which is not a callable type."
        )
    try:
        params = list(inspect.signature(f).parameters.values())
    except ValueError as e:
        return UnsupportedNestedTypeMessage(f"Could not inspect signature of {f}! {e}")

    out = _field_list_from_params(f, params)
    if not isinstance(out, UnsupportedNestedTypeMessage):
        return out

    # Return error message.
    assert isinstance(out, UnsupportedNestedTypeMessage)
    return out


def _field_list_from_params(
    f: Union[Callable, TypeForm[Any]], params: List[inspect.Parameter]
) -> Union[List[FieldDefinition], UnsupportedNestedTypeMessage]:
    # For getting type annotations and docstrings, we can unwrap functools.wraps and
    # functools.partial.
    done = False
    while not done:
        done = True
        if hasattr(f, "__wrapped__"):
            f = f.__wrapped__  # type: ignore
            done = False
        if isinstance(f, functools.partial):
            f = f.func
            done = False

    # Get type annotations, docstrings.
    docstring_from_arg_name = {}

    def populate_docstring_from_arg_name(f):
        docstring = inspect.getdoc(f)
        if docstring is None:
            return
        for param_doc in docstring_parser.parse(docstring).params:
            docstring_from_arg_name[param_doc.arg_name] = param_doc.description

    is_class = hasattr(f, "__init__") and type(f) is type

    populate_docstring_from_arg_name(f)
    if is_class:
        populate_docstring_from_arg_name(f.__init__)

    # This will throw a type error for torch.device, typing.Dict, etc.
    try:
        if is_class:
            hints = get_type_hints(f.__init__, include_extras=True)
        else:
            hints = get_type_hints(f, include_extras=True)
    except TypeError:
        return UnsupportedNestedTypeMessage(f"Could not get hints for {f}!")

    field_list = []
    for param in params:
        # Get default value.
        default = param.default

        # Get helptext from docstring.
        helptext = docstring_from_arg_name.get(param.name)

        # If helptext wasn't in normal docstring, we can search for dataclass-style
        # docstrings.
        if helptext is None and isinstance(f, type):
            helptext = _docstrings.get_field_docstring(f, param.name)

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
            FieldDefinition.make(
                name=param.name,
                # Note that param.annotation doesn't resolve forward references.
                typ=hints[param.name],
                default=default,
                helptext=helptext,
                markers=(_markers.Positional, _markers._PositionalCall)
                if param.kind is inspect.Parameter.POSITIONAL_ONLY
                else (),
            )
        )

    return field_list
