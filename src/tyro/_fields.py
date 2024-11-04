"""Abstractions for pulling out 'field' definitions, which specify inputs, types, and # type: ignore
defaults, from general callables."""

from __future__ import annotations

import contextlib
import dataclasses
import functools
import inspect
import numbers
import warnings
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import docstring_parser
from typing_extensions import Annotated

from . import _resolver, _strings, _unsafe_cache
from ._singleton import DEFAULT_SENTINEL_SINGLETONS, MISSING_SINGLETONS
from ._typing import TypeForm
from .conf import _confstruct, _markers
from .constructors._primitive_spec import (
    PrimitiveConstructorSpec,
    PrimitiveTypeInfo,
    UnsupportedTypeAnnotationError,
)
from .constructors._registry import ConstructorRegistry
from .constructors._struct_spec import StructTypeInfo, UnsupportedStructTypeMessage

global_context_markers: List[Tuple[_markers.Marker, ...]] = []


@dataclasses.dataclass
class FieldDefinition:
    intern_name: str
    extern_name: str
    type_or_callable: Union[TypeForm[Any], Callable]
    default: Any
    # We need to record whether defaults are from default instances to
    # determine if they should override the default in
    # tyro.conf.subcommand(default=...).
    is_default_from_default_instance: bool
    helptext: Optional[str]
    markers: Set[Any]
    custom_constructor: bool

    argconf: _confstruct._ArgConfig
    primitive_spec: PrimitiveConstructorSpec | None

    # Override the name in our kwargs. Useful whenever the user-facing argument name
    # doesn't match the keyword expected by our callable.
    call_argname: Any

    def __post_init__(self):
        if (
            _markers.Fixed in self.markers or _markers.Suppress in self.markers
        ) and self.default in MISSING_SINGLETONS:
            raise UnsupportedTypeAnnotationError(
                f"Field {self.intern_name} is missing a default value!"
            )

    @staticmethod
    @contextlib.contextmanager
    def marker_context(markers: Tuple[_markers.Marker, ...]):
        """Context for setting markers on fields. All fields created within the
        context will have the specified markers."""
        global_context_markers.append(markers)
        yield
        global_context_markers.pop()

    @staticmethod
    def make(
        name: str,
        typ: Union[TypeForm[Any], Callable],
        default: Any,
        is_default_from_default_instance: bool,
        helptext: Optional[str],
        call_argname_override: Optional[Any] = None,
    ):
        # Resolve generics.
        typ = _resolver.TypeParamResolver.concretize_type_params(typ)

        # Narrow types.
        if typ is Any and default not in MISSING_SINGLETONS:
            typ = type(default)
        else:
            # TypeVar constraints are already applied in
            # TypeParamResolver.concretize_type_params(), but that won't be
            # called for functions.
            typ = _resolver.type_from_typevar_constraints(typ)
            typ = _resolver.narrow_collection_types(typ, default)
            typ = _resolver.narrow_union_type(typ, default)

        # Try to extract argconf overrides from type.
        _, argconfs = _resolver.unwrap_annotated(typ, _confstruct._ArgConfig)
        argconf = _confstruct._ArgConfig(
            None,
            None,
            help=None,
            help_behavior_hint=None,
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

        _, primitive_specs = _resolver.unwrap_annotated(typ, PrimitiveConstructorSpec)
        if len(primitive_specs) > 0:
            primitive_spec = primitive_specs[0]
        else:
            primitive_spec = None

        typ, markers = _resolver.unwrap_annotated(typ, _markers._Marker)

        # Include markers set via context manager.
        for context_markers in global_context_markers:
            markers += context_markers

        # Check that the default value matches the final resolved type.
        # There's some similar Union-specific logic for this in narrow_union_type(). We
        # may be able to consolidate this.
        if (
            # Be relatively conservative: isinstance() can be checked on non-type
            # types (like unions in Python >=3.10), but we'll only consider single types
            # for now.
            type(typ) is type
            and not isinstance(default, typ)  # type: ignore
            # If a custom constructor is set, static_type may not be
            # matched to the annotated type.
            and argconf.constructor_factory is None
            and default not in DEFAULT_SENTINEL_SINGLETONS
            # The numeric tower in Python is wacky. This logic is non-critical, so
            # we'll just skip it (+the complexity) for numbers.
            and not isinstance(default, numbers.Number)
        ):
            # If the default value doesn't match the resolved type, we expand the
            # type. This is inspired by https://github.com/brentyi/tyro/issues/88.
            warnings.warn(
                f"The field {name} is annotated with type {typ}, "
                f"but the default value {default} has type {type(default)}. "
                f"We'll try to handle this gracefully, but it may cause unexpected behavior."
            )
            typ = Union[typ, type(default)]  # type: ignore

        out = FieldDefinition(
            intern_name=name,
            extern_name=name if argconf.name is None else argconf.name,
            type_or_callable=(
                typ
                if argconf.constructor_factory is None
                else argconf.constructor_factory()
            ),
            default=default,
            is_default_from_default_instance=is_default_from_default_instance,
            helptext=helptext,
            markers=set(markers),
            custom_constructor=argconf.constructor_factory is not None,
            argconf=argconf,
            call_argname=(
                call_argname_override if call_argname_override is not None else name
            ),
            primitive_spec=primitive_spec,
        )
        return out

    def is_positional(self) -> bool:
        """Returns True if the argument should be positional in the commandline."""
        return (
            # Explicit positionals.
            _markers.Positional in self.markers
            # Dummy dataclasses should have a single positional field.
            or self.intern_name == _strings.dummy_field_name
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
            or self.intern_name == _strings.dummy_field_name
        )


@_unsafe_cache.unsafe_cache(maxsize=1024)
def is_struct_type(typ: Union[TypeForm[Any], Callable], default_instance: Any) -> bool:
    """Determine whether a type should be treated as a 'struct type', where a single
    type can be broken down into multiple fields (eg for nested dataclasses or
    classes).

    TODO: we should come up with a better name than 'struct type', which is a little bit
    misleading."""

    list_or_error = field_list_from_type_or_callable(
        typ, default_instance, support_single_arg_types=False
    )
    return not isinstance(
        list_or_error,
        UnsupportedStructTypeMessage,
    )


def field_list_from_type_or_callable(
    f: Union[Callable, TypeForm[Any]],
    default_instance: Any,
    support_single_arg_types: bool,
) -> (
    UnsupportedStructTypeMessage
    | tuple[Callable | TypeForm[Any], list[FieldDefinition]]
):
    """Generate a list of generic 'field' objects corresponding to the inputs of some
    annotated callable.

    Returns:
        The type that `f` is resolved as.
        A list of field definitions.
    """

    # Apply any custom constructors.
    f = _resolver.swap_type_using_confstruct(f)

    # Concretize generics.
    typevar_context = _resolver.TypeParamResolver.get_assignment_context(f)
    f = typevar_context.origin_type
    with typevar_context:
        registry = ConstructorRegistry._get_active_registry()
        type_info = StructTypeInfo.make(f, default_instance)
        spec = registry.get_struct_spec(type_info)

        with FieldDefinition.marker_context(type_info.markers):
            if not isinstance(spec, UnsupportedStructTypeMessage):
                return f, [
                    FieldDefinition.make(
                        f.name,
                        f.type,
                        f.default,
                        f.is_default_overridden,
                        f.helptext,
                        call_argname_override=f._call_argname,
                    )
                    for f in spec.fields
                ]

            try:
                registry.get_primitive_spec(PrimitiveTypeInfo.make(f, set()))
                is_primitive = True
            except UnsupportedTypeAnnotationError:
                is_primitive = False

            if is_primitive and support_single_arg_types:
                with FieldDefinition.marker_context(
                    (_markers.Positional, _markers._PositionalCall)
                ):
                    return (
                        f,
                        [
                            FieldDefinition.make(
                                name="value",
                                typ=f,
                                default=default_instance,
                                is_default_from_default_instance=True,
                                helptext="",
                            )
                        ],
                    )
            elif not is_primitive and callable(f):
                return _field_list_from_function(
                    type_info.type,  # This will have typing.Annotated metadata stripped.
                    default_instance,
                )

    return UnsupportedStructTypeMessage(f"{f} is not a valid struct type!")


def _field_list_from_function(
    f: Callable, default_instance: Any
) -> UnsupportedStructTypeMessage | tuple[Callable, list[FieldDefinition]]:
    """Generate field lists from non-class callables."""
    try:
        params = list(inspect.signature(f).parameters.values())
    except ValueError:
        return UnsupportedStructTypeMessage(f"Could not get signature for {f}!")

    # Unwrap functools.wraps and functools.partial.
    done = False
    while not done:
        done = True
        if hasattr(f, "__wrapped__"):
            f = f.__wrapped__  # type: ignore
            done = False
        if isinstance(f, functools.partial):
            f = f.func
            done = False

    # Sometime functools.* is applied to a class.
    if inspect.isclass(f):
        if hasattr(f, "__init__") and f.__init__ is not object.__init__:
            f = f.__init__  # type: ignore
        elif hasattr(f, "__new__") and f.__new__ is not object.__new__:
            f = f.__new__

    # Get type annotations, docstrings.
    docstring = inspect.getdoc(f)
    docstring_from_arg_name = {}
    if docstring is not None:
        for param_doc in docstring_parser.parse(docstring).params:
            docstring_from_arg_name[param_doc.arg_name] = param_doc.description
    del docstring

    # This will throw a type error for torch.device, typing.Dict, etc.
    try:
        hints = _resolver.get_type_hints_with_backported_syntax(f, include_extras=True)
    except TypeError:
        return UnsupportedStructTypeMessage(f"Could not get hints for {f}!")

    field_list = []
    for param in params:
        # Get default value.
        default = param.default

        # Get helptext from docstring.
        helptext = docstring_from_arg_name.get(param.name)

        # TODO: re-add.
        # if helptext is None and cls is not None:
        #     helptext = _docstrings.get_field_docstring(cls, param.name)

        if param.name not in hints:
            out = UnsupportedStructTypeMessage(
                f"Expected fully type-annotated callable, but {f} with arguments"
                f" {tuple(map(lambda p: p.name, params))} has no annotation for"
                f" '{param.name}'."
            )
            if param.kind is param.KEYWORD_ONLY:
                # If keyword only: this can't possibly be an instantiator function
                # either, so we escalate to an error.
                raise UnsupportedTypeAnnotationError(out.message)
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

        with FieldDefinition.marker_context(markers):
            field_list.append(
                FieldDefinition.make(
                    name=param.name,
                    # Note that param.annotation doesn't resolve forward references.
                    typ=typ
                    if default_instance in MISSING_SINGLETONS
                    else Annotated.__class_getitem__((typ, _markers._OPTIONAL_GROUP)),
                    default=default,
                    is_default_from_default_instance=False,
                    helptext=helptext,
                )
            )

    return f, field_list
