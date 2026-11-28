"""Abstractions for pulling out 'field' definitions, which specify inputs, types, and # type: ignore
defaults, from general callables."""

from __future__ import annotations

import collections.abc
import enum
import functools
import inspect
import sys
from typing import Any, Callable, Dict, Literal, Tuple, Type

from typing_extensions import (
    Annotated,
    Doc,
    get_args,
    get_origin,
    get_original_bases,
    is_typeddict,
)

from tyro.conf._mutex_group import _MutexGroupConfig
from tyro.constructors._primitive_spec import PrimitiveConstructorSpec

from . import _docstrings, _resolver, _strings, _unsafe_cache
from . import _fmtlib as fmt
from ._record import Record
from ._singleton import MISSING_NONPROP, is_missing, is_sentinel
from ._typing_compat import (
    is_typing_annotated,
    is_typing_literal,
    is_typing_union,
    is_typing_unpack,
)
from .conf import _confstruct, _markers
from .constructors._registry import ConstructorRegistry, check_default_instances
from .constructors._struct_spec import (
    InvalidDefaultInstanceError,
    StructFieldSpec,
    StructTypeInfo,
    UnsupportedStructTypeMessage,
)

_combined_context_markers = _unsafe_cache.make_thread_local_stack(frozenset())
"""Stack of markers that should be applied to all fields. Each element includes all of
the elements before it."""


class _MarkerContext:
    """Context for setting markers on fields. All fields created within the context will
    have the specified markers. This is entered often enough that we avoid the overhead of
    `contextlib.contextmanager`."""

    def __init__(self, markers: tuple[_markers.Marker, ...]) -> None:
        self._markers = markers

    def __enter__(self) -> None:
        current = _combined_context_markers.stack[-1]
        if len(self._markers) > 0:
            current = current.union(self._markers)
        _combined_context_markers.stack.append(current)

    def __exit__(self, *_: Any) -> None:
        _combined_context_markers.stack.pop()


_DEFAULT_ARG_CONFIG = _confstruct._ArgConfig(
    None,
    None,
    help=None,
    help_behavior_hint=None,
    aliases=None,
    prefix_name=True,
    constructor_factory=None,
    default=MISSING_NONPROP,
)


class _AnnotationInfo:
    """Information about a field that can be inferred from only its annotation. This can
    be shared between fields."""

    def __init__(self, typ: Type[Any] | Callable) -> None:
        # Get all Annotated[] metadata.
        # This will unpack types in the form Annotated[type_stripped, *metadata].
        type_stripped, metadata = _resolver.unwrap_annotated(typ, search_type="all")
        self.type_stripped = type_stripped
        self.helptext: str | None = None
        self.argconf = _DEFAULT_ARG_CONFIG
        self.has_argconf = False
        self.markers: frozenset[Any] = frozenset()
        self.mutex_group: _MutexGroupConfig | None = None
        # These can be false positives, but never false negatives.
        self.maybe_narrowable = (
            type_stripped in (list, set, tuple)
            if type(type_stripped) is type
            else not is_typing_union(get_origin(type_stripped))
        )
        self.is_union = is_typing_union(get_origin(type_stripped))
        if len(metadata) == 0:
            return

        # Support PEP 727 Doc objects.
        for x in metadata:
            if isinstance(x, Doc):
                self.helptext = _strings.remove_single_line_breaks(
                    _strings.dedent(x.documentation)
                ).strip()
                break

        # Try to extract argconf overrides from type.
        for overwrite_argconf in metadata:
            if not isinstance(overwrite_argconf, _confstruct._ArgConfig):
                continue
            self.has_argconf = True
            # Apply any annotated argument configuration values.
            update_values = {}
            for name in overwrite_argconf._record_fields:
                value = getattr(overwrite_argconf, name)
                # Handle default specially; we only want to apply it if it's
                # explicitly set (i.e., not MISSING_NONPROP).
                if name == "default":
                    if value is not MISSING_NONPROP:
                        update_values[name] = value
                elif value is not None:
                    update_values[name] = value

            self.argconf = self.argconf.replace(**update_values)
            if self.argconf.help is not None:
                self.helptext = self.argconf.help

        # Get markers.
        self.markers = frozenset(x for x in metadata if isinstance(x, _markers._Marker))
        for x in metadata:
            if isinstance(x, _MutexGroupConfig):
                self.mutex_group = x
                break


_annotation_info_cache: dict[Any, _AnnotationInfo] = _unsafe_cache.make_cache()


class FieldDefinition(Record):
    _record_fields = (
        "intern_name",
        "extern_name",
        "type",
        "type_stripped",
        "default",
        "helptext",
        "markers",
        "custom_constructor",
        "argconf",
        "mutex_group",
        "call_argname",
        "call_mode",
    )

    def __init__(
        self,
        intern_name: str,
        extern_name: str,
        type: Type[Any] | Callable,
        type_stripped: Type[Any] | Callable,
        default: Any,
        helptext: str | Callable[[], str | None] | None,
        markers: frozenset[Any],
        custom_constructor: bool,
        argconf: _confstruct._ArgConfig,
        mutex_group: _MutexGroupConfig | None,
        call_argname: Any,
        call_mode: Literal[
            "kwarg", "positional", "unpack_args", "unpack_kwargs"
        ] = "kwarg",
    ) -> None:
        self.intern_name = intern_name
        self.extern_name = extern_name
        self.type = type
        """Full type, including runtime annotations."""
        self.type_stripped = type_stripped
        self.default = default
        self.helptext = helptext
        self.markers = markers
        self.custom_constructor = custom_constructor

        self.argconf = argconf
        self.mutex_group = mutex_group

        # Override the name in our kwargs. Useful whenever the user-facing argument name
        # doesn't match the keyword expected by our callable.
        self.call_argname = call_argname

        # How this field should be passed to the callable.
        # - "kwarg": passed as keyword argument (default)
        # - "positional": passed as positional argument
        # - "unpack_args": unpacked as *args
        # - "unpack_kwargs": unpacked as **kwargs
        self.call_mode: Literal[
            "kwarg", "positional", "unpack_args", "unpack_kwargs"
        ] = call_mode

    marker_context = _MarkerContext

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
        typ: Type[Any] | Callable,
        default: Any,
        helptext: str | Callable[[], str | None] | None,
        call_argname_override: Any | None = None,
        call_mode: Literal[
            "kwarg", "positional", "unpack_args", "unpack_kwargs"
        ] = "kwarg",
    ) -> FieldDefinition:
        # Narrow types.
        if typ is Any and not is_missing(default):
            typ = type(default)

        key = _unsafe_cache.type_key(typ)
        info = _annotation_info_cache.get(key)
        if info is None:
            info = _AnnotationInfo(typ)
            _annotation_info_cache[key] = info

        if info.helptext is not None:
            helptext = info.helptext

        # Include markers set via context manager.
        markers = _combined_context_markers.stack[-1]
        if len(info.markers) > 0:
            markers = markers | info.markers

        # Only use argconf default if field default is missing.
        argconf = info.argconf
        if default is MISSING_NONPROP and info.has_argconf:
            default = argconf.default

        # Construct field.
        out = FieldDefinition(
            intern_name=name,
            extern_name=name if argconf.name is None else argconf.name,
            type=typ,
            type_stripped=info.type_stripped,
            default=default,
            helptext=helptext,
            markers=markers,
            custom_constructor=argconf.constructor_factory is not None,
            argconf=argconf,
            mutex_group=info.mutex_group,
            call_argname=(
                call_argname_override if call_argname_override is not None else name
            ),
            call_mode=call_mode,
        )

        # Be forgiving about default instances.
        type_stripped = info.type_stripped
        if info.maybe_narrowable:
            type_stripped = _resolver.narrow_collection_types(type_stripped, default)
        if info.is_union and not check_default_instances():
            type_stripped = _resolver.expand_union_types(type_stripped, default)

        if type_stripped is not info.type_stripped:
            return out.with_new_type_stripped(type_stripped)
        else:
            return out

    def with_new_type_stripped(
        self, new_type_stripped: Type[Any] | Callable
    ) -> FieldDefinition:
        if is_typing_annotated(get_origin(self.type)):
            new_type = Annotated[(new_type_stripped, *get_args(self.type)[1:])]  # type: ignore
        else:
            new_type = new_type_stripped  # type: ignore
        return self.replace(
            type=new_type,  # type: ignore
            type_stripped=new_type_stripped,
        )


def _is_primitive_only_collection(
    typ: Any, default_instance: Any, markers: frozenset[Any]
) -> bool:
    """Returns True if `typ` is a subscripted sequence or tuple type that we're certain
    should be treated as a primitive. This mirrors logic in the default struct rules."""
    origin = get_origin(typ)
    args = get_args(typ)
    if len(args) == 0 or Any in args:
        return False

    if origin is tuple and Ellipsis not in args:
        # Fixed-length tuples.
        if not is_sentinel(default_instance) and (
            type(default_instance) is not tuple or len(default_instance) != len(args)
        ):
            return False
    elif origin not in (list, set, tuple, collections.abc.Sequence):
        return False
    elif not is_missing(default_instance) and type(default_instance) not in (
        list,
        set,
        tuple,
    ):
        return False

    for arg in args:
        if arg is Ellipsis:
            continue
        spec = ConstructorRegistry.get_primitive_spec_from_annotation(arg, markers)
        if not isinstance(spec, PrimitiveConstructorSpec) or spec.nargs == "*":
            return False
    return True


def _is_struct_type_fast(typ: Any, default_instance: Any) -> bool | None:
    """Avoid the cost of building a field list for common types. Returns `None` if we
    should take the slow path instead."""

    # Fast path: common primitive types are never struct types.
    if type(typ) is type and typ in (int, str, float, bool, bytes, type(None)):
        return False

    # Users can define arbitrary struct rules.
    if ConstructorRegistry._has_custom_rules() or check_default_instances():
        return None

    typ_stripped, metadata = _resolver.unwrap_annotated(typ, "all")
    for x in metadata:
        if isinstance(x, PrimitiveConstructorSpec):
            return False
        if isinstance(x, _confstruct._SubcommandConfig):
            # Will impact the default value.
            return None

    if isinstance(typ_stripped, type):
        # Note that we care about both dataclasses and subclasses of dataclasses.
        if hasattr(typ_stripped, "__dataclass_fields__"):
            return True
        if (
            isinstance(typ_stripped, enum.EnumMeta)
            or typ_stripped.__module__.partition(".")[0] == "pathlib"
        ) and not issubclass(typ_stripped, tuple):
            return False
        return None

    origin = get_origin(typ_stripped)
    if is_typing_union(origin) or is_typing_literal(origin):
        # These are supported by the primitive rules, and ignored by the struct rules.
        spec = ConstructorRegistry.get_primitive_spec_from_annotation(typ, frozenset())
        return False if isinstance(spec, PrimitiveConstructorSpec) else None

    markers = frozenset(x for x in metadata if isinstance(x, _markers._Marker))
    if _is_primitive_only_collection(typ_stripped, default_instance, markers):
        return False
    return None


def is_struct_type(
    typ: Type[Any] | Callable, default_instance: Any, in_union_context: bool
) -> bool:
    """Determine whether a type should be treated as a 'struct type', where a single
    type can be broken down into multiple fields (eg for nested dataclasses or
    classes).

    The `in_union_context` flag indicates whether this type is being evaluated as part
    of a union. When True, allows collection types like List[Struct] or Dict[str, Struct]
    without defaults to be treated as struct types (for subcommand creation).
    """

    maybe_out = _is_struct_type_fast(typ, default_instance)
    if maybe_out is not None:
        return maybe_out

    list_or_error = field_list_from_type_or_callable(
        typ,
        default_instance,
        support_single_arg_types=False,
        in_union_context=in_union_context,
    )
    return not isinstance(
        list_or_error,
        (UnsupportedStructTypeMessage, InvalidDefaultInstanceError),
    )


def field_list_from_type_or_callable(
    f: Callable | Type[Any],
    default_instance: Any,
    support_single_arg_types: bool,
    in_union_context: bool,
) -> (
    UnsupportedStructTypeMessage
    | InvalidDefaultInstanceError
    | tuple[Callable | Type[Any], list[FieldDefinition]]
):
    """Generate a list of generic 'field' objects corresponding to the inputs of some
    annotated callable.

    The `in_union_context` flag indicates whether this type is being evaluated as part
    of a union. When True, allows collection types like List[Struct] or Dict[str, Struct]
    without defaults to be treated as struct types (for subcommand creation).

    Returns:
        - tuple[type, list[FieldDefinition]] if successful: the resolved type and its field definitions.
        - UnsupportedStructTypeMessage if the type cannot be treated as a struct (e.g., not a dataclass, function, etc.).
        - InvalidDefaultInstanceError if the type can be treated as a struct, but the provided default instance is incompatible with the type.
    """
    if (type(f) is not type or hasattr(f, "__tyro_markers__")) and len(
        _resolver.unwrap_annotated(f, PrimitiveConstructorSpec)[1]
    ) > 0:
        return UnsupportedStructTypeMessage(
            lambda f=f: f"{f} should be parsed as a primitive type."
        )

    type_info = StructTypeInfo.make(f, default_instance, in_union_context)
    type_orig = f
    del f

    # Special case when treating `None` as a struct type.
    if support_single_arg_types and type_info.type is type(None):
        if not is_missing(default_instance) and default_instance is not None:
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

            is_primitive = ConstructorRegistry._is_primitive_type(
                type_orig, frozenset()
            )
            if is_primitive and support_single_arg_types:
                with FieldDefinition.marker_context((_markers.Positional,)):
                    return (
                        lambda x: x,
                        [
                            FieldDefinition.make(
                                name="value",
                                typ=type_orig,
                                default=default_instance,
                                helptext="",
                                call_mode="positional",
                            )
                        ],
                    )
            elif not is_primitive and callable(type_info.type):
                return _field_list_from_function(
                    type_info.type,  # This will have typing.Annotated metadata stripped.
                    default_instance,
                    markers=type_info.markers,
                )

    return UnsupportedStructTypeMessage(
        lambda: f"{type_orig} is not a valid struct type!"
    )


def _field_list_from_function(
    f: Callable, default_instance: Any, markers: tuple[_markers.Marker, ...]
) -> UnsupportedStructTypeMessage | tuple[Callable, list[FieldDefinition]]:
    """Generate field lists from callables."""

    # Development note: separate conditions are helpful for test coverage reports.
    if f is Any:
        return UnsupportedStructTypeMessage("`Any` is not a valid struct type!")

    f_origin = get_origin(f)
    if getattr(f_origin, "__module__", None) in ("collections.abc", "builtins"):
        return UnsupportedStructTypeMessage(
            lambda: f"`{f}` is not a valid struct type!"
        )

    try:
        params = list(inspect.signature(f).parameters.values())
    except ValueError:
        return UnsupportedStructTypeMessage(lambda: f"Could not get signature for {f}!")

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

    # Parse docstrings lazily. This function will be shared by all of the arguments.
    docstring_from_arg_name: dict[str, str | None] | None = None

    def get_param_helptext(name: str) -> str | None:
        nonlocal docstring_from_arg_name
        if docstring_from_arg_name is None:
            docstring_from_arg_name = _docstrings.parse_params_from_docstring(
                inspect.getdoc(f)
            )
        helptext = docstring_from_arg_name.get(name)
        if helptext is None and inspect.isclass(f_before_init_unwrap):
            helptext = _docstrings.get_field_docstring(
                f_before_init_unwrap, name, markers
            )
        return helptext

    # Get hints if we haven't done it already.
    # This will throw a type error for torch.device, typing.Dict, etc.
    if hints is None:
        try:
            hints = _resolver.get_type_hints_resolve_type_params(f, include_extras=True)
        except TypeError:
            return UnsupportedStructTypeMessage(lambda: f"Could not get hints for {f}!")

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
        return UnsupportedStructTypeMessage(lambda: f"Empty hints for {f}!")

    field_list = []
    for param in params:
        # Get default value.
        default = param.default

        # Get helptext from docstring.
        helptext = functools.partial(get_param_helptext, param.name)

        # Set call_mode and markers for positional + variadic arguments.
        func_markers: Tuple[Any, ...] = ()
        call_mode: Literal["kwarg", "positional", "unpack_args", "unpack_kwargs"] = (
            "kwarg"
        )
        typ: Any = hints.get(param.name, Any)
        if param.kind is inspect.Parameter.POSITIONAL_ONLY:
            func_markers = (_markers.Positional,)
            call_mode = "positional"
        elif param.kind is inspect.Parameter.VAR_POSITIONAL:
            # Handle *args signatures.
            #
            # This will create a `--args T [T ...]` CLI argument.
            call_mode = "unpack_args"
            # Extract markers from annotation before wrapping in Tuple,
            # otherwise markers like Positional get buried inside the
            # Tuple type and are lost.
            _, extracted_metadata = _resolver.unwrap_annotated(typ, search_type="all")
            func_markers = func_markers + tuple(
                x for x in extracted_metadata if isinstance(x, _markers._Marker)
            )
            typ = Tuple[(typ, ...)]  # type: ignore
            # Only set empty default when there's no default_instance.
            # When default_instance is provided, we want MISSING_NONPROP so that
            # the _OPTIONAL_GROUP logic can return the default_instance directly.
            if is_missing(default_instance):
                default = ()
        elif param.kind is inspect.Parameter.VAR_KEYWORD:
            # Handle **kwargs signatures.
            call_mode = "unpack_kwargs"
            typ_origin = get_origin(typ)
            unpack_args = get_args(typ)

            # Check for Unpack[TypedDict] pattern.
            if (
                is_typing_unpack(typ_origin)
                and len(unpack_args) == 1
                and is_typeddict(unpack_args[0])
            ):
                # Treat as nested TypedDict struct.
                typ = unpack_args[0]
                default = MISSING_NONPROP  # Let TypedDict rule handle defaults.
            else:
                # Original behavior: creates `--kwargs STR T [STR T ...]` argument.
                typ = Dict[str, typ]  # type: ignore
                # Only set the empty default when there's no default_instance,
                # so the _OPTIONAL_GROUP logic can return the provided default
                # directly (mirrors the *args branch above). Without this guard
                # a `default=` instance for a **kwargs parameter is dropped.
                if is_missing(default_instance):
                    default = {}

        with FieldDefinition.marker_context(func_markers):
            field_list.append(
                FieldDefinition.make(
                    name=param.name,
                    # param.annotation doesn't resolve forward references.
                    typ=typ
                    if is_missing(default_instance)
                    else Annotated[(typ, _markers._OPTIONAL_GROUP)],  # type: ignore
                    default=default if default is not param.empty else MISSING_NONPROP,
                    helptext=helptext,
                    call_mode=call_mode,
                )
            )

    return f_out, field_list
