"""Abstractions for pulling out 'field' definitions, which specify inputs, types, and # type: ignore
defaults, from general callables."""

from __future__ import annotations

import contextlib
import dataclasses
import functools
import inspect
import sys
from typing import Any, Callable, Dict, Tuple

import docstring_parser
from typing_extensions import Annotated, Doc, get_args, get_origin, get_original_bases

from tyro.conf._mutex_group import _MutexGroupConfig

from . import _docstrings, _resolver, _strings, _unsafe_cache
from . import _fmtlib as fmt
from ._singleton import MISSING_AND_MISSING_NONPROP, MISSING_NONPROP
from ._typing import TypeForm
from ._typing_compat import is_typing_annotated
from .conf import _confstruct, _markers
from .constructors._registry import ConstructorRegistry, check_default_instances
from .constructors._struct_spec import (
    InvalidDefaultInstanceError,
    StructFieldSpec,
    StructTypeInfo,
    UnsupportedStructTypeMessage,
)

global_context_markers: list[tuple[_markers.Marker, ...]] = []


@dataclasses.dataclass
class FieldDefinition:
    intern_name: str
    extern_name: str
    type: TypeForm[Any] | Callable
    """Full type, including runtime annotations."""
    type_stripped: TypeForm[Any] | Callable
    default: Any
    helptext: str | None
    markers: set[Any]
    custom_constructor: bool

    argconf: _confstruct._ArgConfig
    mutex_group: _MutexGroupConfig | None

    # Override the name in our kwargs. Useful whenever the user-facing argument name
    # doesn't match the keyword expected by our callable.
    call_argname: Any

    @staticmethod
    @contextlib.contextmanager
    def marker_context(markers: tuple[_markers.Marker, ...]):
        """Context for setting markers on fields. All fields created within the
        context will have the specified markers."""
        global_context_markers.append(markers)
        try:
            yield
        finally:
            global_context_markers.pop()

    @staticmethod
    def from_field_spec(field_spec: StructFieldSpec) -> FieldDefinition:
        return FieldDefinition.make(
            name=field_spec.name,
            typ=field_spec.type,
            default=field_spec.default,
            helptext=field_spec.helptext,
            call_argname_override=field_spec._call_argname,
        )

    @staticmethod
    def make(
        name: str,
        typ: TypeForm[Any] | Callable,
        default: Any,
        helptext: str | None,
        call_argname_override: Any | None = None,
    ):
        # Narrow types.
        if typ is Any and default not in MISSING_AND_MISSING_NONPROP:
            typ = type(default)

        # Get all Annotated[] metadata.
        # This will unpack types in the form Annotated[type_stripped, *metadata].
        type_stripped, metadata = _resolver.unwrap_annotated(typ, search_type="all")

        # Support PEP 727 Doc objects.
        doc_objs = tuple(x for x in metadata if isinstance(x, Doc))
        if len(doc_objs) > 0:
            helptext = _strings.remove_single_line_breaks(
                _strings.dedent(doc_objs[0].documentation)
            ).strip()

        # Try to extract argconf overrides from type.
        argconfs = tuple(x for x in metadata if isinstance(x, _confstruct._ArgConfig))
        argconf = _confstruct._ArgConfig(
            None,
            None,
            help=None,
            help_behavior_hint=None,
            aliases=None,
            prefix_name=True,
            constructor_factory=None,
            default=MISSING_NONPROP,
        )
        for overwrite_argconf in argconfs:
            # Apply any annotated argument configuration values.
            update_values = {}
            for field in dataclasses.fields(overwrite_argconf):
                value = getattr(overwrite_argconf, field.name)
                # Handle default specially; we only want to apply it if it's
                # explicitly set (i.e., not MISSING_NONPROP).
                if field.name == "default":
                    if value is not MISSING_NONPROP:
                        update_values[field.name] = value
                elif value is not None:
                    update_values[field.name] = value

            argconf = dataclasses.replace(argconf, **update_values)
            if argconf.help is not None:
                helptext = argconf.help

        # Get markers.
        markers = tuple(x for x in metadata if isinstance(x, _markers._Marker))
        mutually_exclusive_groups = tuple(
            x for x in metadata if isinstance(x, _MutexGroupConfig)
        )

        # Include markers set via context manager.
        for context_markers in global_context_markers:
            markers += context_markers

        # Only use argconf default if field default is missing.
        if default is MISSING_NONPROP and len(argconfs) > 0:
            default = argconf.default

        # Construct field.
        out = FieldDefinition(
            intern_name=name,
            extern_name=name if argconf.name is None else argconf.name,
            type=typ,
            type_stripped=type_stripped,
            default=default,
            helptext=helptext,
            markers=set(markers),
            custom_constructor=argconf.constructor_factory is not None,
            argconf=argconf,
            mutex_group=mutually_exclusive_groups[0]
            if len(mutually_exclusive_groups) > 0
            else None,
            call_argname=(
                call_argname_override if call_argname_override is not None else name
            ),
        )

        # Be forgiving about default instances.
        type_stripped = _resolver.narrow_collection_types(type_stripped, default)
        if not check_default_instances():
            type_stripped = _resolver.expand_union_types(type_stripped, default)

        if type_stripped != out.type_stripped:
            return out.with_new_type_stripped(type_stripped)
        else:
            return out

    def with_new_type_stripped(
        self, new_type_stripped: TypeForm[Any] | Callable
    ) -> FieldDefinition:
        if is_typing_annotated(get_origin(self.type)):
            new_type = Annotated[(new_type_stripped, *get_args(self.type)[1:])]  # type: ignore
        else:
            new_type = new_type_stripped  # type: ignore
        return dataclasses.replace(
            self,
            type=new_type,  # type: ignore
            type_stripped=new_type_stripped,
        )

    def is_positional_call(self) -> bool:
        """Returns True if the argument should be positional in underlying Python call."""
        return _markers._PositionalCall in self.markers


@_unsafe_cache.unsafe_cache(maxsize=1024)
def is_struct_type(typ: TypeForm[Any] | Callable, default_instance: Any) -> bool:
    """Determine whether a type should be treated as a 'struct type', where a single
    type can be broken down into multiple fields (eg for nested dataclasses or
    classes)."""

    list_or_error = field_list_from_type_or_callable(
        typ, default_instance, support_single_arg_types=False
    )
    return not isinstance(
        list_or_error,
        (UnsupportedStructTypeMessage, InvalidDefaultInstanceError),
    )


def field_list_from_type_or_callable(
    f: Callable | TypeForm[Any],
    default_instance: Any,
    support_single_arg_types: bool,
) -> (
    UnsupportedStructTypeMessage
    | InvalidDefaultInstanceError
    | tuple[Callable | TypeForm[Any], list[FieldDefinition]]
):
    """Generate a list of generic 'field' objects corresponding to the inputs of some
    annotated callable.

    Returns:
        - tuple[type, list[FieldDefinition]] if successful: the resolved type and its field definitions.
        - UnsupportedStructTypeMessage if the type cannot be treated as a struct (e.g., not a dataclass, function, etc.).
        - InvalidDefaultInstanceError if the type can be treated as a struct, but the provided default instance is incompatible with the type.
    """
    type_info = StructTypeInfo.make(f, default_instance)
    type_orig = f
    del f

    # Special case when treating `None` as a struct type.
    if support_single_arg_types and type_info.type is type(None):
        if (
            default_instance not in MISSING_AND_MISSING_NONPROP
            and default_instance is not None
        ):
            return InvalidDefaultInstanceError(
                (
                    fmt.text(
                        "Default type ",
                        fmt.text["cyan"](str(type(default_instance))),
                        " is not ",
                        fmt.text["magenta"]("None"),
                    ),
                )
            )
        return (lambda: None, [])

    with type_info._typevar_context:
        spec = ConstructorRegistry.get_struct_spec(type_info)

        # Check if we got an error instead of a spec.
        if isinstance(spec, InvalidDefaultInstanceError):
            return spec

        with FieldDefinition.marker_context(type_info.markers):
            if spec is not None:
                return spec.instantiate, [
                    FieldDefinition.from_field_spec(f) for f in spec.fields
                ]

            is_primitive = ConstructorRegistry._is_primitive_type(type_orig, set())
            if is_primitive and support_single_arg_types:
                with FieldDefinition.marker_context(
                    (_markers.Positional, _markers._PositionalCall)
                ):
                    return (
                        lambda x: x,
                        [
                            FieldDefinition.make(
                                name="value",
                                typ=type_orig,
                                default=default_instance,
                                helptext="",
                            )
                        ],
                    )
            elif not is_primitive and callable(type_info.type):
                return _field_list_from_function(
                    type_info.type,  # This will have typing.Annotated metadata stripped.
                    default_instance,
                    markers=type_info.markers,
                )

    return UnsupportedStructTypeMessage(f"{type_orig} is not a valid struct type!")


def _field_list_from_function(
    f: Callable, default_instance: Any, markers: tuple[_markers.Marker, ...]
) -> UnsupportedStructTypeMessage | tuple[Callable, list[FieldDefinition]]:
    """Generate field lists from callables."""

    # Development note: separate conditions are helpful for test coverage reports.
    if f is Any:
        return UnsupportedStructTypeMessage("`Any` is not a valid struct type!")

    f_origin = get_origin(f)
    if getattr(f_origin, "__module__", None) in ("collections.abc", "builtins"):
        return UnsupportedStructTypeMessage(f"`{f}` is not a valid struct type!")

    try:
        params = list(inspect.signature(f).parameters.values())
    except ValueError:
        return UnsupportedStructTypeMessage(f"Could not get signature for {f}!")

    # `f` that is called (output) may be different from what we want to
    # inspect.
    f_out = f

    # Unwrap functools.wraps and functools.partial.
    done = False
    functools_marker = False
    while not done:
        done = True
        if hasattr(f, "__wrapped__"):
            f = f.__wrapped__  # type: ignore
            done = False
            functools_marker = True
        if isinstance(f, functools.partial):
            f = f.func
            done = False
            functools_marker = True

    # Check for abstract classes.
    if inspect.isabstract(f):
        return UnsupportedStructTypeMessage("Abstract classes cannot be instantiated!")

    # If `f` is class, we want to inspect its __init__ method for the
    # signature. But the docstrings may still be in the class signature itself.
    f_before_init_unwrap = f

    hints = None

    if inspect.isclass(f):
        signature_func = None
        if hasattr(f, "__init__") and f.__init__ is not object.__init__:
            signature_func = "__init__"
        elif hasattr(f, "__new__") and f.__new__ is not object.__new__:
            signature_func = "__new__"

        if signature_func is not None:
            # Get the __init__ / __new__ method from the class, as well as the
            # class that contains it.
            #
            # We call this the "signature function", because it's the function
            # that we use to instantiate the class.
            orig_cls = f
            base_cls_with_signature = None
            for base_cls_with_signature in inspect.getmro(f):
                if signature_func in base_cls_with_signature.__dict__:
                    f = getattr(base_cls_with_signature, signature_func)
                    break
            assert base_cls_with_signature is not None
            assert f is not orig_cls

            # For older versions of Python, the signature returned above (when
            # passed through generics base classes) will sometimes be (*args,
            # **kwargs).
            #
            # This is a hack. We can remove it if we deprecate Python 3.8 support.
            if sys.version_info < (3, 9) and not functools_marker:  # pragma: no cover
                params = list(inspect.signature(f).parameters.values())[1:]

            # Get hints for the signature function by recursing through the
            # inheritance tree. This is needed to correctly resolve type
            # parameters, which can be set anywhere between the input class and
            # the class where the __init__ or __new__ method is defined.
            def get_hints_for_signature_func(cls):
                typevar_context = _resolver.TypeParamResolver.get_assignment_context(
                    cls
                )
                cls = typevar_context.origin_type
                with typevar_context:
                    if cls is base_cls_with_signature:
                        return _resolver.get_type_hints_resolve_type_params(
                            f, include_extras=True
                        )
                    for base_cls in get_original_bases(cls):
                        if not issubclass(
                            _resolver.unwrap_origin_strip_extras(base_cls),
                            base_cls_with_signature,
                        ):
                            continue
                        return get_hints_for_signature_func(
                            _resolver.TypeParamResolver.resolve_params_and_aliases(
                                base_cls
                            )
                        )

                assert False, (
                    "We couldn't find the base class. This seems like a bug in tyro."
                )

            hints = get_hints_for_signature_func(orig_cls)

    # Early return for lambda functions.
    if getattr(f, "__name__", None) == "<lambda>" and len(params) > 0:
        return UnsupportedStructTypeMessage(
            "Lambda functions cannot be type-annotated!"
        )

    # Get type annotations, docstrings.
    docstring = inspect.getdoc(f)
    docstring_from_arg_name = {}
    if docstring is not None:
        for param_doc in docstring_parser.parse(docstring).params:
            docstring_from_arg_name[param_doc.arg_name] = param_doc.description
    del docstring

    # Get hints if we haven't done it already.
    # This will throw a type error for torch.device, typing.Dict, etc.
    if hints is None:
        try:
            hints = _resolver.get_type_hints_resolve_type_params(f, include_extras=True)
        except TypeError:
            return UnsupportedStructTypeMessage(f"Could not get hints for {f}!")

    # Expect non-empty type hints from classes.
    #
    # Generally we can be more forgiving with functions, for example
    #
    #     def main(x = 3) -> None: ...
    #
    # we can parse as if `x` was annotated with int. But if we have:
    #
    #     def main(x: SomeScaryType = SomeScaryDefault) -> None: ...
    #
    # we'll be more conservative in converting `--x` to a {fixed} argument.
    # The latter case requires returning an UnsupportedStructTypeMessage to avoid
    # unpacking the arguments of SomeScaryType.
    if (len(hints) == 0 or len(params) == 0) and not inspect.isfunction(
        f_before_init_unwrap
    ):
        return UnsupportedStructTypeMessage(f"Empty hints for {f}!")

    field_list = []
    for param in params:
        # Get default value.
        default = param.default

        # Get helptext from docstring.
        helptext = docstring_from_arg_name.get(param.name)
        if helptext is None and inspect.isclass(f_before_init_unwrap):
            helptext = _docstrings.get_field_docstring(
                f_before_init_unwrap, param.name, markers
            )

        # Set markers for positional + variadic arguments.
        func_markers: Tuple[Any, ...] = ()
        typ: Any = hints.get(param.name, Any)
        if param.kind is inspect.Parameter.POSITIONAL_ONLY:
            func_markers = (_markers.Positional, _markers._PositionalCall)
        elif param.kind is inspect.Parameter.VAR_POSITIONAL:
            # Handle *args signatures.
            #
            # This will create a `--args T [T ...]` CLI argument.
            func_markers = (_markers._UnpackArgsCall,)
            typ = Tuple[(typ, ...)]  # type: ignore
            default = ()
        elif param.kind is inspect.Parameter.VAR_KEYWORD:
            # Handle *kwargs signatures.
            #
            # This will create a `--kwargs STR T [STR T ...]` CLI argument.
            #
            # It would be straightforward to make both this and *args truly
            # positional, omitting the --args/--kwargs prefix, but we are
            # choosing not to because it would make *args and **kwargs
            # difficult to use in conjunction.
            func_markers = (_markers._UnpackKwargsCall,)
            typ = Dict[str, typ]  # type: ignore
            default = {}

        with FieldDefinition.marker_context(func_markers):
            field_list.append(
                FieldDefinition.make(
                    name=param.name,
                    # param.annotation doesn't resolve forward references.
                    typ=typ
                    if default_instance in MISSING_AND_MISSING_NONPROP
                    else Annotated[(typ, _markers._OPTIONAL_GROUP)],  # type: ignore
                    default=default if default is not param.empty else MISSING_NONPROP,
                    helptext=helptext,
                )
            )

    return f_out, field_list
