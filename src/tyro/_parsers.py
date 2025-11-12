"""Interface for generating `argparse.ArgumentParser()` definitions from callables."""

from __future__ import annotations

import dataclasses
import numbers
import warnings
from typing import Any, Callable, Dict, List, Set, Tuple, Type, TypeVar, Union, cast

from typing_extensions import Annotated, get_args, get_origin

from tyro.constructors._registry import ConstructorRegistry
from tyro.constructors._struct_spec import (
    InvalidDefaultInstanceError,
    UnsupportedStructTypeMessage,
)

from . import (
    _arguments,
    _docstrings,
    _fields,
    _resolver,
    _singleton,
    _strings,
    _subcommand_matching,
)
from . import _fmtlib as fmt
from ._typing import TypeForm
from ._typing_compat import is_typing_union
from .conf import _confstruct, _markers
from .constructors._primitive_spec import (
    PrimitiveConstructorSpec,
    UnsupportedTypeAnnotationError,
)

T = TypeVar("T")


@dataclasses.dataclass
class LazyParserSpecification:
    """Lazy wrapper that defers full ParserSpecification creation until needed.

    Stores lightweight metadata (description) for fast help text generation,
    while deferring expensive parser construction until actually needed.
    """

    # Lightweight field needed for tyro help formatting.
    description: str

    # Factory for creating the full parser when needed.
    _factory: Callable[[], ParserSpecification]
    _cached: ParserSpecification | None = dataclasses.field(default=None, init=False)

    def evaluate(self) -> ParserSpecification:
        """Get the full ParserSpecification, creating it if needed."""
        if self._cached is None:
            self._cached = self._factory()
        return self._cached


@dataclasses.dataclass
class ArgWithContext:
    arg: _arguments.ArgumentDefinition
    source_parser: ParserSpecification
    """ParserSpecification that directly contains this argument."""
    local_root_parser: ParserSpecification
    """Furthest ancestor of `source_parser` within the same (sub)command."""


@dataclasses.dataclass(frozen=True)
class ParserSpecification:
    """Each parser contains a list of arguments and optionally some subparsers."""

    f: Callable
    markers: Set[_markers._Marker]
    description: str
    args: List[_arguments.ArgumentDefinition]
    field_list: List[_fields.FieldDefinition]
    child_from_prefix: Dict[str, ParserSpecification]
    helptext_from_intern_prefixed_field_name: Dict[str, str | None]

    # Subparser groups that are direct children of this parser. The actual tree
    # structure for argparse is built on-demand in apply().
    subparsers_from_intern_prefix: Dict[str, SubparsersSpecification]
    intern_prefix: str
    extern_prefix: str
    has_required_args: bool
    subparser_parent: ParserSpecification | None
    prog_suffix: str

    @staticmethod
    def from_callable_or_type(
        f: Callable[..., T],
        markers: Set[_markers._Marker],
        description: str | None,
        parent_classes: Set[Type[Any]],
        default_instance: Union[
            T, _singleton.PropagatingMissingType, _singleton.NonpropagatingMissingType
        ],
        intern_prefix: str,
        extern_prefix: str,
        subcommand_prefix: str,
        support_single_arg_types: bool,
        prog_suffix: str,
    ) -> ParserSpecification:
        """Create a parser definition from a callable or type."""

        # Consolidate subcommand types.
        f_unwrapped, new_markers = _resolver.unwrap_annotated(f, _markers._Marker)
        markers = markers | set(new_markers)

        # Cycle detection.
        #
        # - `parent` here refers to in the nesting hierarchy, not the superclass.
        # - We threshold by `max_nesting_depth` to suppress false positives,
        #   for example from custom constructors that behave differently
        #   depending the default value. (example: ml_collections.ConfigDict)
        max_nesting_depth = 128
        if (
            f in parent_classes
            and f is not dict
            and intern_prefix.count(".") > max_nesting_depth
        ):
            raise UnsupportedTypeAnnotationError(
                f"Found a cyclic dependency with type {f}."
            )

        # TODO: we are abusing the (minor) distinctions between types, classes, and
        # callables throughout the code. This is mostly for legacy reasons, could be
        # cleaned up.
        parent_classes = parent_classes | {cast(Type, f)}

        # Wrap our type with a dummy dataclass if it can't be treated as a
        # nested type. For example: passing in f=int will result in a dataclass
        # with a single field typed as int.
        #
        # Why don't we always use a dummy dataclass?
        # => Docstrings for inner structs are currently lost when we nest struct types.
        from . import _calling

        if not _fields.is_struct_type(
            cast(type, f), default_instance
        ) and f_unwrapped is not type(None):
            f = _calling.DummyWrapper[f]  # type: ignore
            default_instance = _calling.DummyWrapper(default_instance)  # type: ignore

        # Resolve the type of `f`, generate a field list.
        with _fields.FieldDefinition.marker_context(tuple(markers)):
            out = _fields.field_list_from_type_or_callable(
                f=f,
                default_instance=default_instance,
                support_single_arg_types=support_single_arg_types,
            )
            assert not isinstance(out, UnsupportedStructTypeMessage), out.message
            assert not isinstance(out, InvalidDefaultInstanceError), "\n".join(
                repr(fmt.rows(*out.message))
            )
            f, field_list = out

        has_required_args = False
        args: list[_arguments.ArgumentDefinition] = []
        helptext_from_intern_prefixed_field_name: Dict[str, str | None] = {}

        child_from_prefix: Dict[str, ParserSpecification] = {}

        subparsers_from_prefix = {}

        for field in field_list:
            field_out = handle_field(
                field,
                parent_classes=parent_classes,
                intern_prefix=intern_prefix,
                extern_prefix=extern_prefix,
                subcommand_prefix=subcommand_prefix,
                prog_suffix=prog_suffix,
            )
            if isinstance(field_out, _arguments.ArgumentDefinition):
                # Handle single arguments.
                args.append(field_out)
                if field_out.lowered.required:
                    has_required_args = True
            elif isinstance(field_out, SubparsersSpecification):
                # Handle subparsers.
                subparsers_from_prefix[field_out.intern_prefix] = field_out
            elif isinstance(field_out, ParserSpecification):
                # Handle nested parsers.
                nested_parser = field_out
                child_from_prefix[field_out.intern_prefix] = nested_parser

                # Flatten subparsers from nested parser into current parser.
                # This handles the case where a field's type has subcommands that need
                # to be accessible at the parent level.
                for (
                    prefix,
                    subparser_spec,
                ) in nested_parser.subparsers_from_intern_prefix.items():
                    subparsers_from_prefix[prefix] = subparser_spec

                if nested_parser.has_required_args:
                    has_required_args = True

                # Helptext for this field; used as description for grouping arguments.
                class_field_name = _strings.make_field_name(
                    [intern_prefix, field.intern_name]
                )
                if field.helptext is not None:
                    helptext_from_intern_prefixed_field_name[class_field_name] = (
                        field.helptext
                    )
                else:
                    helptext_from_intern_prefixed_field_name[class_field_name] = (
                        _docstrings.get_callable_description(nested_parser.f)
                    )

                # If arguments are in an optional group, it indicates that the default_instance
                # will be used if none of the arguments are passed in.
                if (
                    len(nested_parser.args) >= 1
                    and _markers._OPTIONAL_GROUP in nested_parser.args[0].field.markers
                ):
                    current_helptext = helptext_from_intern_prefixed_field_name[
                        class_field_name
                    ]
                    helptext_from_intern_prefixed_field_name[class_field_name] = (
                        ("" if current_helptext is None else current_helptext + "\n\n")
                        + "Default: "
                        + str(field.default)
                    )

        parser_spec = ParserSpecification(
            f=f,
            markers=markers,
            description=_strings.remove_single_line_breaks(
                description
                if description is not None
                else _docstrings.get_callable_description(f)
            ),
            args=args,
            field_list=field_list,
            child_from_prefix=child_from_prefix,
            helptext_from_intern_prefixed_field_name=helptext_from_intern_prefixed_field_name,
            subparsers_from_intern_prefix=subparsers_from_prefix,
            intern_prefix=intern_prefix,
            extern_prefix=extern_prefix,
            has_required_args=has_required_args,
            subparser_parent=None,
            prog_suffix=prog_suffix,
        )

        return parser_spec

    def get_args_including_children(
        self,
        local_root: ParserSpecification | None = None,
    ) -> list[ArgWithContext]:
        """Get all arguments in this parser and its children.

        Does not include arguments in subparsers.
        """
        if local_root is None:
            local_root = self
        args = [ArgWithContext(arg, self, local_root) for arg in self.args]
        for child in self.child_from_prefix.values():
            args.extend(child.get_args_including_children(local_root))
        return args


def handle_field(
    field: _fields.FieldDefinition,
    parent_classes: Set[Type[Any]],
    intern_prefix: str,
    extern_prefix: str,
    subcommand_prefix: str,
    prog_suffix: str,
) -> Union[
    _arguments.ArgumentDefinition,
    ParserSpecification,
    SubparsersSpecification,
]:
    """Determine what to do with a single field definition."""

    # Check that the default value matches the final resolved type.
    # There's some similar Union-specific logic for this in narrow_union_type(). We
    # may be able to consolidate this.
    if (
        not _resolver.is_instance(field.type_stripped, field.default)
        # If a custom constructor is set, static_type may not be
        # matched to the annotated type.
        and field.argconf.constructor_factory is None
        and field.default not in _singleton.DEFAULT_SENTINEL_SINGLETONS
        # The numeric tower in Python is wacky. This logic is non-critical, so
        # we'll just skip it (+the complexity) for numbers.
        and not isinstance(field.default, numbers.Number)
    ):
        # If the default value doesn't match the resolved type, we expand the
        # type. This is inspired by https://github.com/brentyi/tyro/issues/88.
        field_name = _strings.make_field_name([extern_prefix, field.extern_name])
        message = (
            f"The field `{field_name}` is annotated with type `{field.type}`, "
            f"but the default value `{field.default}` has type `{type(field.default)}`. "
            f"We'll try to handle this gracefully, but it may cause unexpected behavior."
        )
        warnings.warn(message)
        field = field.with_new_type_stripped(
            Union[field.type_stripped, type(field.default)]  # type: ignore
        )

    # Force primitive if (1) the field is annotated with a primitive constructor spec, or (2) if
    # a custom primitive exists for the type.
    force_primitive = (
        len(_resolver.unwrap_annotated(field.type, PrimitiveConstructorSpec)[1]) > 0
    ) or ConstructorRegistry._is_primitive_type(
        field.type, field.markers, nondefault_only=True
    )

    if not force_primitive:
        # (1) Handle Unions over callables; these result in subparsers.
        if _markers.Suppress not in field.markers:
            subparsers_attempt = SubparsersSpecification.from_field(
                field,
                parent_classes=parent_classes,
                intern_prefix=_strings.make_field_name(
                    [intern_prefix, field.intern_name]
                ),
                extern_prefix=_strings.make_field_name(
                    [extern_prefix, field.extern_name]
                ),
                prog_suffix=prog_suffix,
            )
            if subparsers_attempt is not None:
                return subparsers_attempt

        # (2) Handle nested callables.
        if _fields.is_struct_type(field.type, field.default):
            return ParserSpecification.from_callable_or_type(
                field.type_stripped,
                markers=field.markers,
                description=field.helptext,
                parent_classes=parent_classes,
                default_instance=field.default,
                intern_prefix=_strings.make_field_name(
                    [intern_prefix, field.intern_name]
                ),
                extern_prefix=(
                    _strings.make_field_name([extern_prefix, field.extern_name])
                    if field.argconf.prefix_name in (True, None)
                    else field.extern_name
                ),
                subcommand_prefix=subcommand_prefix,
                support_single_arg_types=False,
                prog_suffix=prog_suffix,
            )

    # (3) Handle primitive or fixed types. These produce a single argument!
    return _arguments.ArgumentDefinition(
        intern_prefix=intern_prefix,
        extern_prefix=extern_prefix,
        subcommand_prefix=subcommand_prefix,
        field=field,
    )


@dataclasses.dataclass(frozen=True)
class SubparsersSpecification:
    """Structure for defining subparsers. Each subparser is a parser with a name."""

    description: str | None
    parser_from_name: Dict[str, LazyParserSpecification]
    default_name: str | None
    default_parser: ParserSpecification | None
    intern_prefix: str
    extern_prefix: str
    required: bool
    default_instance: Any
    options: Tuple[Union[TypeForm[Any], Callable], ...]
    prog_suffix: str

    @staticmethod
    def from_field(
        field: _fields.FieldDefinition,
        parent_classes: Set[Type[Any]],
        intern_prefix: str,
        extern_prefix: str,
        prog_suffix: str,
    ) -> SubparsersSpecification | ParserSpecification | None:
        """From a field: return either a subparser specification, a parser
        specification for subcommands when `tyro.conf.AvoidSubcommands` is used
        and a default is set, or `None` if the field does not create a
        subparser."""
        # Union of classes should create subparsers.
        typ = _resolver.unwrap_annotated(field.type_stripped)
        if not is_typing_union(get_origin(typ)):
            return None

        # We don't use sets here to retain order of subcommands.
        options: List[Union[type, Callable]]
        options = [typ for typ in get_args(typ)]

        # If specified, swap types using tyro.conf.subcommand(constructor=...).
        found_subcommand_conf = False
        for i, option in enumerate(options):
            _, found_subcommand_configs = _resolver.unwrap_annotated(
                option, _confstruct._SubcommandConfig
            )
            if (
                len(found_subcommand_configs) > 0
                and found_subcommand_configs[0].constructor_factory is not None
            ):
                found_subcommand_conf = True
                options[i] = Annotated[  # type: ignore
                    (
                        found_subcommand_configs[0].constructor_factory(),
                        *_resolver.unwrap_annotated(option, "all")[1],
                    )
                ]

        # Exit if we don't contain any struct types.
        def recursive_contains_struct_type(options: list[Any]) -> bool:
            for o in options:
                if _fields.is_struct_type(o, _singleton.MISSING_NONPROP):
                    return True
                if is_typing_union(get_origin(_resolver.unwrap_annotated(o))):
                    if recursive_contains_struct_type(get_args(o)):  # type: ignore
                        return True
            return False

        if not found_subcommand_conf and not recursive_contains_struct_type(options):
            return None

        # Get subcommand configurations from `tyro.conf.subcommand()`.
        subcommand_config_from_name: Dict[str, _confstruct._SubcommandConfig] = {}
        subcommand_type_from_name: Dict[str, type] = {}
        subcommand_names: list[str] = []
        for option in options:
            option_unwrapped, found_subcommand_configs = _resolver.unwrap_annotated(
                option, _confstruct._SubcommandConfig
            )
            subcommand_name = _strings.subparser_name_from_type(
                (
                    ""
                    if _markers.OmitSubcommandPrefixes in field.markers
                    else extern_prefix
                ),
                cast(type, option),
            )
            subcommand_names.append(subcommand_name)
            if subcommand_name in subcommand_type_from_name:
                # Raise a warning that the subcommand already exists
                original_type = subcommand_type_from_name[subcommand_name]
                original_type_full_name = (
                    f"{original_type.__module__}.{original_type.__name__}"
                )
                new_type_full_name = (
                    f"{option_unwrapped.__module__}.{option_unwrapped.__name__}"
                    if option_unwrapped is not None
                    else "none"
                )

                warnings.warn(
                    f"Duplicate subcommand name detected: '{subcommand_name}' is already used for "
                    f"{original_type_full_name} but will be overwritten by {new_type_full_name}. "
                    f"Only the last type ({new_type_full_name}) will be accessible via this subcommand. "
                    f"Consider using distinct class names or use tyro.conf.subcommand() to specify "
                    f"explicit subcommand names."
                )
            if len(found_subcommand_configs) != 0:
                # Explicitly annotated default.
                assert len(found_subcommand_configs) == 1, (
                    f"Expected only one subcommand config, but {subcommand_name} has"
                    f" {len(found_subcommand_configs)}."
                )
                subcommand_config_from_name[subcommand_name] = found_subcommand_configs[
                    0
                ]
            subcommand_type_from_name[subcommand_name] = cast(type, option)

        # If a field default is provided, try to find a matching subcommand name.
        default_name = (
            _subcommand_matching.match_subcommand(
                field.default,
                subcommand_config_from_name,
                subcommand_type_from_name,
                extern_prefix,
            )
            if field.default not in _singleton.MISSING_AND_MISSING_NONPROP
            else None
        )

        # Handle `tyro.conf.AvoidSubcommands` with a default value.
        if default_name is not None and _markers.AvoidSubcommands in field.markers:
            return ParserSpecification.from_callable_or_type(
                subcommand_type_from_name[default_name],
                markers=field.markers,
                description=None,
                parent_classes=parent_classes,
                default_instance=field.default,
                intern_prefix=intern_prefix,
                extern_prefix=extern_prefix,
                subcommand_prefix=extern_prefix,
                support_single_arg_types=True,
                prog_suffix=prog_suffix,
            )

        # Add subcommands for each option.
        parser_from_name: Dict[str, LazyParserSpecification] = {}
        for option, subcommand_name in zip(options, subcommand_names):
            # Get a subcommand config: either pulled from the type annotations or the
            # field default.
            if subcommand_name in subcommand_config_from_name:
                subcommand_config = subcommand_config_from_name[subcommand_name]
            else:
                subcommand_config = _confstruct._SubcommandConfig(
                    "unused",
                    description=None,
                    default=_singleton.MISSING_NONPROP,
                    prefix_name=True,
                    constructor_factory=None,
                )

            # If names match, borrow subcommand default from field default.
            if default_name == subcommand_name and (
                field.default not in _singleton.MISSING_AND_MISSING_NONPROP
            ):
                subcommand_config = dataclasses.replace(
                    subcommand_config, default=field.default
                )

            # Strip the subcommand config from the option type.
            # Relevant: https://github.com/brentyi/tyro/pull/117
            option_unwrapped, annotations = _resolver.unwrap_annotated(option, "all")
            annotations = tuple(
                a
                for a in annotations
                if not isinstance(a, _confstruct._SubcommandConfig)
            )
            if _markers.Suppress in annotations:
                continue

            if len(annotations) == 0:
                option = option_unwrapped
            else:
                option = Annotated[(option_unwrapped,) + annotations]  # type: ignore

            # Extract description early for fast help text generation.
            # If no explicit description, get it from the callable's docstring.
            description_for_help = subcommand_config.description
            if option_unwrapped is type(None):
                description_for_help = ""
            elif description_for_help is None:
                description_for_help = _docstrings.get_callable_description(
                    option_unwrapped
                )

            # Create lazy parser: defer expensive parsing until actually needed.
            def parser_factory(
                option_captured: Any = option,
                markers_captured: Set[_markers._Marker] = field.markers,
                subcommand_config_captured: _confstruct._SubcommandConfig = subcommand_config,
                parent_classes_captured: Set[Type[Any]] = parent_classes,
                intern_prefix_captured: str = intern_prefix,
                extern_prefix_captured: str = extern_prefix,
                prog_suffix_captured: str = prog_suffix,
                subcommand_name_captured: str = subcommand_name,
                field_markers_captured: Set[_markers._Marker] = field.markers,
            ) -> ParserSpecification:
                with _fields.FieldDefinition.marker_context(
                    tuple(field_markers_captured)
                ):
                    subparser = ParserSpecification.from_callable_or_type(
                        option_captured,  # type: ignore
                        markers=markers_captured,
                        description=subcommand_config_captured.description,
                        parent_classes=parent_classes_captured,
                        default_instance=subcommand_config_captured.default,
                        intern_prefix=intern_prefix_captured,
                        extern_prefix=extern_prefix_captured,
                        subcommand_prefix=extern_prefix_captured,
                        support_single_arg_types=True,
                        prog_suffix=subcommand_name_captured
                        if prog_suffix_captured == ""
                        else prog_suffix_captured + " " + subcommand_name_captured,
                    )
                # Apply prefix to helptext in nested classes in subparsers.
                subparser = dataclasses.replace(
                    subparser,
                    helptext_from_intern_prefixed_field_name={
                        _strings.make_field_name([intern_prefix_captured, k]): v
                        for k, v in subparser.helptext_from_intern_prefixed_field_name.items()
                    },
                )
                return subparser

            parser_from_name[subcommand_name] = LazyParserSpecification(
                description=_strings.remove_single_line_breaks(description_for_help),
                _factory=parser_factory,  # type: ignore
            )

        # Default parser was suppressed!
        if default_name not in parser_from_name:
            default_name = None

        # Required if a default is passed in, but the default value has missing
        # parameters.
        default_parser = None
        if default_name is None:
            required = True
        else:
            required = False
            # Evaluate the lazy parser to check for required args/subparsers.
            default_parser_evaluated = parser_from_name[default_name].evaluate()

            # If there are any required arguments.
            if any(
                map(lambda arg: arg.lowered.required, default_parser_evaluated.args)
            ):
                required = True
                default_parser = None
            # If there are any required subparsers.
            elif any(
                subparser_spec.required
                for subparser_spec in default_parser_evaluated.subparsers_from_intern_prefix.values()
            ):
                required = True
                default_parser = None
            else:
                default_parser = default_parser_evaluated

        return SubparsersSpecification(
            # If we wanted, we could add information about the default instance
            # automatically, as is done for normal fields. But for now we just rely on
            # the user to include it in the docstring.
            description=field.helptext,
            parser_from_name=parser_from_name,
            default_name=default_name,
            default_parser=default_parser,
            intern_prefix=intern_prefix,
            extern_prefix=extern_prefix,
            required=required,
            default_instance=field.default,
            options=tuple(options),
            prog_suffix=prog_suffix,
        )
