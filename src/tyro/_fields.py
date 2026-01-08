"""Abstractions for pulling out 'field' definitions, which specify inputs, types, and # type: ignore
defaults, from general callables."""

from __future__ import annotations

import dataclasses
import functools
import inspect
import sys
from typing import Any, Callable, Dict, Literal, Tuple
from typing import Type as TypeForm

import docstring_parser
from typing_extensions import (
    Annotated,
    Doc,
    get_args,
    get_origin,
    get_original_bases,
    is_typeddict,
)

from . import _docstrings, _resolver, _strings, _unsafe_cache
from . import _fmtlib as fmt
from ._normalized_type import NormalizedType
from ._singleton import MISSING_NONPROP, is_missing
from ._typing_compat import is_typing_unpack
from .conf import _confstruct, _markers
from .conf._mutex_group import _MutexGroupConfig
from .constructors._primitive_spec import PrimitiveConstructorSpec
from .constructors._registry import ConstructorRegistry, check_default_instances
from .constructors._struct_spec import (
    InvalidDefaultInstanceError,
    StructFieldSpec,
    StructTypeInfo,
    UnsupportedStructTypeMessage,
)


@dataclasses.dataclass
class FieldDefinition:
    intern_name: str
    extern_name: str
    normalized_type: NormalizedType
    """Normalized type with Annotated stripped and markers/metadata extracted.
    Access .type for the inner type, .markers for markers, .metadata for other metadata."""
    default: Any
    helptext: str | Callable[[], str | None] | None
    custom_constructor: bool

    argconf: _confstruct._ArgConfig
    mutex_group: _MutexGroupConfig | None

    # Override the name in our kwargs. Useful whenever the user-facing argument name
    # doesn't match the keyword expected by our callable.
    call_argname: Any

    # How this field should be passed to the callable.
    # - "kwarg": passed as keyword argument (default)
    # - "positional": passed as positional argument
    # - "unpack_args": unpacked as *args
    # - "unpack_kwargs": unpacked as **kwargs
    call_mode: Literal["kwarg", "positional", "unpack_args", "unpack_kwargs"] = "kwarg"

    @staticmethod
    def from_field_spec(
        field_spec: StructFieldSpec, inherit_markers: tuple[Any, ...] = ()
    ) -> FieldDefinition:
        return FieldDefinition.make(
            name=field_spec.name,
            typ=field_spec.type,
            default=field_spec.default,
            helptext=field_spec.helptext,
            call_argname_override=field_spec._call_argname,
            inherit_markers=inherit_markers,
        )

    @staticmethod
    def make(
        name: str,
        typ: TypeForm[Any] | Callable,
        default: Any,
        helptext: str | Callable[[], str | None] | None,
        call_argname_override: Any | None = None,
        call_mode: Literal[
            "kwarg", "positional", "unpack_args", "unpack_kwargs"
        ] = "kwarg",
        inherit_markers: tuple[Any, ...] = (),
    ):
        # Narrow types.
        if typ is Any and not is_missing(default):
            typ = type(default)

        # Normalize the type - strips Annotated and extracts markers/metadata.
        normalized = NormalizedType.from_type(typ, inherit_markers=inherit_markers)
        metadata = normalized.metadata

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

        # Get mutex groups from metadata.
        mutually_exclusive_groups = tuple(
            x for x in metadata if isinstance(x, _MutexGroupConfig)
        )

        # Only use argconf default if field default is missing.
        if default is MISSING_NONPROP and len(argconfs) > 0:
            default = argconf.default

        # Construct field.
        out = FieldDefinition(
            intern_name=name,
            extern_name=name if argconf.name is None else argconf.name,
            normalized_type=normalized,
            default=default,
            helptext=helptext,
            custom_constructor=argconf.constructor_factory is not None,
            argconf=argconf,
            mutex_group=mutually_exclusive_groups[0]
            if len(mutually_exclusive_groups) > 0
            else None,
            call_argname=(
                call_argname_override if call_argname_override is not None else name
            ),
            call_mode=call_mode,
        )

        # Be forgiving about default instances.
        type_stripped = _resolver.narrow_collection_types(normalized.type, default)
        if not check_default_instances():
            type_stripped = _resolver.expand_union_types(type_stripped, default)

        if type_stripped != out.normalized_type.type:
            return out.with_new_type_stripped(type_stripped)
        else:
            return out

    def with_new_type_stripped(
        self, new_type_stripped: TypeForm[Any] | Callable
    ) -> FieldDefinition:
        # Re-normalize the new type to get proper type_args.
        # We pass the existing markers so they're preserved.
        new_normalized = NormalizedType.from_type(
            new_type_stripped, inherit_markers=self.normalized_type.markers
        )
        # Preserve metadata from original type.
        new_normalized = dataclasses.replace(
            new_normalized,
            metadata=self.normalized_type.metadata,
        )

        return dataclasses.replace(
            self,
            normalized_type=new_normalized,
        )


@_unsafe_cache.unsafe_cache(maxsize=1024)
def is_struct_type(
    typ: TypeForm[Any] | Callable,
    default_instance: Any,
    in_union_context: bool,
    inherit_markers: tuple[Any, ...] = (),
) -> bool:
    """Determine whether a type should be treated as a 'struct type', where a single
    type can be broken down into multiple fields (eg for nested dataclasses or
    classes).

    The `in_union_context` flag indicates whether this type is being evaluated as part
    of a union. When True, allows collection types like List[Struct] or Dict[str, Struct]
    without defaults to be treated as struct types (for subcommand creation).
    """

    # Fast path: common primitive types are never struct types.
    if type(typ) is type and typ in (int, str, float, bool, bytes, type(None)):
        return False

    list_or_error = field_list_from_type_or_callable(
        typ,
        default_instance,
        support_single_arg_types=False,
        in_union_context=in_union_context,
        inherit_markers=inherit_markers,
    )
    return not isinstance(
        list_or_error,
        (UnsupportedStructTypeMessage, InvalidDefaultInstanceError),
    )


def field_list_from_type_or_callable(
    f: Callable | TypeForm[Any],
    default_instance: Any,
    support_single_arg_types: bool,
    in_union_context: bool,
    inherit_markers: tuple[Any, ...] = (),
) -> (
    UnsupportedStructTypeMessage
    | InvalidDefaultInstanceError
    | tuple[Callable | TypeForm[Any], list[FieldDefinition]]
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
    # Normalize the type to extract markers and metadata.
    normalized = NormalizedType.from_type(f, inherit_markers=inherit_markers)

    # Check if this type has a PrimitiveConstructorSpec attached - if so, treat as primitive.
    if any(isinstance(m, PrimitiveConstructorSpec) for m in normalized.metadata):
        return UnsupportedStructTypeMessage(
            f"{f} should be parsed as a primitive type."
        )

    type_info = StructTypeInfo.make(normalized, default_instance, in_union_context)
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

    with type_info.typevar_context:
        spec = ConstructorRegistry.get_struct_spec(type_info)

        # Check if we got an error instead of a spec.
        if isinstance(spec, InvalidDefaultInstanceError):
            return spec

        if spec is not None:
            return spec.instantiate, [
                FieldDefinition.from_field_spec(f, inherit_markers=type_info.markers)
                for f in spec.fields
            ]

        is_primitive = ConstructorRegistry._is_primitive_type(type_orig, ())
        if is_primitive and support_single_arg_types:
            return (
                lambda x: x,
                [
                    FieldDefinition.make(
                        name="value",
                        typ=type_orig,
                        default=default_instance,
                        helptext="",
                        call_mode="positional",
                        inherit_markers=type_info.markers + (_markers.Positional,),
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
            # Lazy docstring parsing: use partial to defer expensive parsing.
            helptext = functools.partial(
                _docstrings.get_field_docstring,
                f_before_init_unwrap,
                param.name,
                markers,
            )

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
                default = {}

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
                inherit_markers=markers + func_markers,
            )
        )

    return f_out, field_list
