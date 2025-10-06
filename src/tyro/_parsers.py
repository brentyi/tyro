"""Interface for generating `argparse.ArgumentParser()` definitions from callables."""

from __future__ import annotations

import dataclasses
import numbers
import warnings
from typing import Any, Callable, Dict, List, Set, Tuple, Type, TypeVar, Union, cast

from rich.text import Text
from typing_extensions import Annotated, get_args, get_origin

from tyro.constructors._registry import ConstructorRegistry
from tyro.constructors._struct_spec import UnsupportedStructTypeMessage

from . import _argparse as argparse
from . import (
    _argparse_formatter,
    _arguments,
    _docstrings,
    _fields,
    _resolver,
    _singleton,
    _strings,
    _subcommand_matching,
)
from ._typing import TypeForm
from ._typing_compat import is_typing_union
from .conf import _confstruct, _markers
from .conf._mutex_group import _MutexGroupConfig
from .constructors._primitive_spec import (
    PrimitiveConstructorSpec,
    UnsupportedTypeAnnotationError,
)

T = TypeVar("T")


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

    # We have two mechanics for tracking subparser groups:
    # - A single subparser group, which is what gets added in the tree structure built
    # by the argparse parser.
    subparsers: SubparsersSpecification | None
    # - A set of subparser groups, which reflect the tree structure built by the
    # hierarchy of a nested config structure.
    subparsers_from_intern_prefix: Dict[str, SubparsersSpecification]
    intern_prefix: str
    extern_prefix: str
    has_required_args: bool
    consolidate_subcommand_args: bool
    add_help: bool

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
        add_help: bool,
        subcommand_prefix: str = "",
        support_single_arg_types: bool = False,
    ) -> ParserSpecification:
        """Create a parser definition from a callable or type."""

        # Consolidate subcommand types.
        markers = markers | set(_resolver.unwrap_annotated(f, _markers._Marker)[1])
        consolidate_subcommand_args = _markers.ConsolidateSubcommandArgs in markers

        # Cycle detection.
        #
        # - 'parent' here refers to in the nesting hierarchy, not the superclass.
        # - We threshold by `max_nesting_depth` to suppress false positives,
        #  for example from custom constructors that behave differently
        #  depending the default value. (example: ml_collections.ConfigDict)
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

        # Resolve the type of `f`, generate a field list.
        with _fields.FieldDefinition.marker_context(tuple(markers)):
            out = _fields.field_list_from_type_or_callable(
                f=f,
                default_instance=default_instance,
                support_single_arg_types=support_single_arg_types,
            )
            assert not isinstance(out, UnsupportedStructTypeMessage), out
            f, field_list = out

        has_required_args = False
        args = []
        helptext_from_intern_prefixed_field_name: Dict[str, str | None] = {}

        child_from_prefix: Dict[str, ParserSpecification] = {}

        subparsers = None
        subparsers_from_prefix = {}

        for field in field_list:
            field_out = handle_field(
                field,
                parent_classes=parent_classes,
                intern_prefix=intern_prefix,
                extern_prefix=extern_prefix,
                subcommand_prefix=subcommand_prefix,
                add_help=add_help,
            )
            if isinstance(field_out, _arguments.ArgumentDefinition):
                # Handle single arguments.
                args.append(field_out)
                if field_out.lowered.required:
                    has_required_args = True
            elif isinstance(field_out, SubparsersSpecification):
                # Handle subparsers.
                subparsers_from_prefix[field_out.intern_prefix] = field_out
                subparsers = add_subparsers_to_leaves(subparsers, field_out)
            elif isinstance(field_out, ParserSpecification):
                # Handle nested parsers.
                nested_parser = field_out
                child_from_prefix[field_out.intern_prefix] = nested_parser

                if nested_parser.has_required_args:
                    has_required_args = True

                # Include nested subparsers.
                if nested_parser.subparsers is not None:
                    subparsers_from_prefix.update(
                        nested_parser.subparsers_from_intern_prefix
                    )
                    subparsers = add_subparsers_to_leaves(
                        subparsers, nested_parser.subparsers
                    )

                # Helptext for this field; used as description for grouping arguments.
                class_field_name = _strings.make_intern_prefix(
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

        return ParserSpecification(
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
            subparsers=subparsers,
            subparsers_from_intern_prefix=subparsers_from_prefix,
            intern_prefix=intern_prefix,
            extern_prefix=extern_prefix,
            has_required_args=has_required_args,
            consolidate_subcommand_args=consolidate_subcommand_args,
            add_help=add_help,
        )

    def apply(
        self, parser: argparse.ArgumentParser, force_required_subparsers: bool
    ) -> Tuple[argparse.ArgumentParser, ...]:
        """Create defined arguments and subparsers."""

        # Generate helptext.
        parser.description = self.description

        # `force_required_subparsers`: if we have required arguments and we're
        # consolidating all arguments into the leaves of the subparser trees, a
        # required argument in one node of this tree means that all of its
        # descendants are required.
        if self.consolidate_subcommand_args and self.has_required_args:
            force_required_subparsers = True

        # Create subparser tree.
        subparser_group = None
        if self.subparsers is not None:
            leaves = self.subparsers.apply(parser, force_required_subparsers)
            subparser_group = parser._action_groups.pop()
        else:
            leaves = (parser,)

        # Depending on whether we want to consolidate subcommand args, we can either
        # apply arguments to the intermediate parser or only on the leaves.
        if self.consolidate_subcommand_args:
            for leaf in leaves:
                self.apply_args(leaf)
        else:
            self.apply_args(parser)

        if subparser_group is not None:
            parser._action_groups.append(subparser_group)

        # Break some API boundaries to rename the "optional arguments" => "options".
        assert parser._action_groups[1].title in (
            # python <= 3.9
            "optional arguments",
            # python >= 3.10
            "options",
        )
        parser._action_groups[1].title = "options"

        return leaves

    def apply_args(
        self,
        parser: argparse.ArgumentParser,
        parent: ParserSpecification | None = None,
        exclusive_group_from_group_conf: Dict[
            _MutexGroupConfig, argparse._MutuallyExclusiveGroup
        ]
        | None = None,
    ) -> None:
        """Create defined arguments and subparsers."""

        # Make argument groups.
        def format_group_name(group_name: str) -> str:
            return (group_name + " options").strip()

        group_from_group_name: Dict[str, argparse._ArgumentGroup] = {
            "": parser._action_groups[1],
            **{
                cast(str, group.title).partition(" ")[0]: group
                for group in parser._action_groups[2:]
            },
        }
        positional_group = parser._action_groups[0]
        assert positional_group.title == "positional arguments"

        # Inherit mutex groups from parent or create new dict
        if exclusive_group_from_group_conf is None:
            exclusive_group_from_group_conf = {}

        # Add each argument group. Groups with only suppressed arguments won't
        # be added.
        for arg in self.args:
            # Don't add suppressed arguments to the parser.
            if arg.is_suppressed():
                continue
            elif arg.field.is_positional():
                arg.add_argument(positional_group)
                continue
            elif arg.field.mutex_group is not None:
                group_conf = arg.field.mutex_group
                if group_conf not in exclusive_group_from_group_conf:
                    exclusive_group_from_group_conf[group_conf] = (
                        parser.add_argument_group(
                            "mutually exclusive",
                            description=_argparse_formatter.str_from_rich(
                                Text.from_markup(
                                    "Exactly one argument must be passed in. [bright_red](required)[/bright_red]"
                                )
                            )
                            if group_conf.required
                            else "At most one argument can overridden.",
                        ).add_mutually_exclusive_group(required=group_conf.required)
                    )
                arg.add_argument(exclusive_group_from_group_conf[group_conf])
            else:
                group_name = (
                    arg.extern_prefix
                    if arg.field.argconf.name != ""
                    # If the field name is "erased", we'll place the argument in
                    # the parent's group.
                    #
                    # This is to avoid "issue 1" in:
                    # https://github.com/brentyi/tyro/issues/183
                    #
                    # Setting `tyro.conf.arg(name="")` should generally be
                    # discouraged, so this will rarely matter.
                    else arg.extern_prefix.rpartition(".")[0]
                )
                if group_name not in group_from_group_name:
                    description = (
                        parent.helptext_from_intern_prefixed_field_name.get(
                            arg.intern_prefix
                        )
                        if parent is not None
                        else None
                    )
                    group_from_group_name[group_name] = parser.add_argument_group(
                        format_group_name(group_name),
                        description=description,
                    )
                arg.add_argument(group_from_group_name[group_name])

        for child in self.child_from_prefix.values():
            child.apply_args(
                parser,
                parent=self,
                exclusive_group_from_group_conf=exclusive_group_from_group_conf,
            )


def handle_field(
    field: _fields.FieldDefinition,
    parent_classes: Set[Type[Any]],
    intern_prefix: str,
    extern_prefix: str,
    subcommand_prefix: str,
    add_help: bool,
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
        field_name = _strings.make_extern_prefix([extern_prefix, field.extern_name])
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
            # Use make_intern_prefix for internal argparse dest names (no delimiter swapping).
            intern_prefix_for_subparser = _strings.make_intern_prefix(
                [intern_prefix, field.intern_name]
            )

            subparsers_attempt = SubparsersSpecification.from_field(
                field,
                parent_classes=parent_classes,
                intern_prefix=intern_prefix_for_subparser,
                extern_prefix=_strings.make_extern_prefix(
                    [extern_prefix, field.extern_name]
                ),
                add_help=add_help,
            )
            if subparsers_attempt is not None:
                return subparsers_attempt

        # (2) Handle nested callables.
        if _fields.is_struct_type(field.type, field.default):
            return ParserSpecification.from_callable_or_type(
                field.type_stripped,
                markers=field.markers,
                description=None,
                parent_classes=parent_classes,
                default_instance=field.default,
                intern_prefix=_strings.make_intern_prefix(
                    [intern_prefix, field.intern_name]
                ),
                extern_prefix=(
                    _strings.make_extern_prefix([extern_prefix, field.extern_name])
                    if field.argconf.prefix_name in (True, None)
                    else field.extern_name
                ),
                add_help=add_help,
                subcommand_prefix=subcommand_prefix,
                support_single_arg_types=False,
            )

    # (3) Handle primitive or fixed types. These produce a single argument!
    return _arguments.ArgumentDefinition(
        intern_prefix=intern_prefix,
        extern_prefix=extern_prefix,
        subcommand_prefix=subcommand_prefix,
        field=field,
    )


@dataclasses.dataclass(frozen=True)
class _SubcommandEntry:
    """Internal helper for organizing subcommand information."""
    name: str
    config: _confstruct._SubcommandConfig
    parser_type: Any
    type_for_matching: Any
    uses_wrapper: bool
    intern_prefix: str
    extern_prefix: str
    subcommand_prefix: str


@dataclasses.dataclass(frozen=True)
class SubparsersSpecification:
    """Structure for defining subparsers. Each subparser is a parser with a name."""

    name: str
    description: str | None
    parser_from_name: Dict[str, ParserSpecification]
    default_name: str | None
    default_parser: ParserSpecification | None
    intern_prefix: str
    required: bool
    default_instance: Any
    options: Tuple[Union[TypeForm[Any], Callable], ...]

    @staticmethod
    def from_field(
        field: _fields.FieldDefinition,
        parent_classes: Set[Type[Any]],
        intern_prefix: str,
        extern_prefix: str,
        add_help: bool,
    ) -> SubparsersSpecification | ParserSpecification | None:
        """From a field: return either a subparser specification, a parser
        specification for subcommands when `tyro.conf.AvoidSubcommands` is used
        and a default is set, or `None` if the field does not create a
        subparser."""
        # Union of classes should create subparsers.
        typ = _resolver.unwrap_annotated(field.type_stripped)
        if not is_typing_union(get_origin(typ)):
            return None

        _, union_level_configs = _resolver.unwrap_annotated(
            field.type, _confstruct._SubcommandConfig
        )

        collected_options: List[Any] = []

        def _collect(option: Any, inherited: Tuple[Any, ...]) -> None:
            option_origin, annotations_all = _resolver.unwrap_annotated(option, "all")
            configs = tuple(
                a for a in annotations_all if isinstance(a, _confstruct._SubcommandConfig)
            )
            other_annotations = inherited + tuple(
                a for a in annotations_all if not isinstance(a, _confstruct._SubcommandConfig)
            )

            if len(configs) > 0:
                assert len(configs) == 1, (
                    "Expected at most one tyro.conf.subcommand() annotation, found "
                    f"{len(configs)}."
                )
                annotated = option_origin
                if len(other_annotations) > 0:
                    annotated = Annotated[(annotated,) + other_annotations]  # type: ignore
                collected_options.append(Annotated[(annotated,) + configs])  # type: ignore
                return

            if is_typing_union(get_origin(option_origin)):
                for inner in get_args(option_origin):
                    _collect(inner, other_annotations)
                return

            if option_origin is type(None):
                annotations_to_apply = inherited + other_annotations
                annotated: Any = option_origin
                if len(annotations_to_apply) > 0:
                    annotated = Annotated[(option_origin,) + annotations_to_apply]  # type: ignore
                collected_options.append(annotated)
                return

            annotated = option_origin
            if len(other_annotations) > 0:
                annotated = Annotated[(annotated,) + other_annotations]  # type: ignore
            collected_options.append(annotated)

        for variant in get_args(typ):
            _collect(variant, ())

        options: List[Union[type, Callable]] = []
        for option in collected_options:
            if option is type(None):
                options.append(cast(Callable, none_proxy))
            else:
                options.append(option)

        # Respect constructor overrides provided via tyro.conf.subcommand().
        for i, option in enumerate(options):
            if option is none_proxy:
                continue
            _, configs = _resolver.unwrap_annotated(option, _confstruct._SubcommandConfig)
            if len(configs) > 0 and configs[0].constructor_factory is not None:
                options[i] = Annotated[  # type: ignore
                    (
                        configs[0].constructor_factory(),
                        *_resolver.unwrap_annotated(option, "all")[1],
                    )
                ]

        if not any(
            option is not none_proxy
            and (
                _fields.is_struct_type(
                    cast(type, _resolver.unwrap_annotated(option, "all")[0]),
                    _singleton.MISSING_NONPROP,
                )
                or is_typing_union(
                    get_origin(_resolver.unwrap_annotated(option, "all")[0])
                )
            )
            for option in options
        ):
            return None

        prefix_for_name = (
            "" if _markers.OmitSubcommandPrefixes in field.markers else extern_prefix
        )

        subcommand_entries: List[_SubcommandEntry] = []
        subcommand_type_from_name: Dict[str, Any] = {}
        subcommand_config_from_name: Dict[str, _confstruct._SubcommandConfig] = {}

        for index, option in enumerate(options):
            if option is none_proxy:
                subcommand_name = _strings.subparser_name_from_type(prefix_for_name, type(None))
                config = _confstruct._SubcommandConfig(
                    "unused",
                    description=None,
                    default=_singleton.MISSING_NONPROP,
                    prefix_name=True,
                    constructor_factory=None,
                )
                subcommand_config_from_name[subcommand_name] = config
                subcommand_type_from_name[subcommand_name] = option
                subcommand_entries.append(
                    _SubcommandEntry(
                        name=subcommand_name,
                        config=config,
                        parser_type=option,
                        type_for_matching=option,
                        uses_wrapper=False,
                        intern_prefix=intern_prefix,
                        extern_prefix="" if _markers.OmitSubcommandPrefixes in field.markers else extern_prefix,
                        subcommand_prefix="" if _markers.OmitSubcommandPrefixes in field.markers else intern_prefix,
                    )
                )
                continue

            option_origin, annotations_all = _resolver.unwrap_annotated(option, "all")
            configs = tuple(
                a for a in annotations_all if isinstance(a, _confstruct._SubcommandConfig)
            )
            other_annotations = tuple(
                a for a in annotations_all if not isinstance(a, _confstruct._SubcommandConfig)
            )

            subcommand_name = _strings.subparser_name_from_type(
                prefix_for_name,
                cast(type, option),
            )

            config = (
                configs[0]
                if len(configs) > 0
                else _confstruct._SubcommandConfig(
                    "unused",
                    description=None,
                    default=_singleton.MISSING_NONPROP,
                    prefix_name=True,
                    constructor_factory=None,
                )
            )

            base_type: Any = (
                config.constructor_factory() if config.constructor_factory else option_origin
            )
            annotated_type: Any = base_type
            if len(other_annotations) > 0:
                annotated_type = Annotated[(base_type,) + other_annotations]  # type: ignore

            if subcommand_name in subcommand_type_from_name:
                original_type = subcommand_type_from_name[subcommand_name]
                warnings.warn(
                    f"Duplicate subcommand name detected: '{subcommand_name}' is already used for "
                    f"{original_type} but will be overwritten by {annotated_type}. "
                    f"Only the last type ({annotated_type}) will be accessible via this subcommand. "
                    f"Consider using distinct class names or use tyro.conf.subcommand() to specify explicit subcommand names."
                )

            subcommand_config_from_name[subcommand_name] = config
            subcommand_type_from_name[subcommand_name] = annotated_type

            if _markers.Suppress in other_annotations:
                continue

            uses_wrapper = is_typing_union(get_origin(base_type))
            if uses_wrapper:
                sanitized = subcommand_name.replace("-", "_").replace(":", "_")
                parser_type = _strings.create_dummy_wrapper(
                    annotated_type,
                    cls_name=f"tyro_dummy_{sanitized if len(sanitized) > 0 else index}",
                )
                # Dummy wrappers: use subcommand name as intern_prefix, empty for extern/subcommand.
                entry_intern_prefix = subcommand_name
                entry_extern_prefix = ""
                entry_subcommand_prefix = ""
            else:
                parser_type = annotated_type
                # Regular: inherit parent prefixes (respecting OmitSubcommandPrefixes).
                entry_intern_prefix = intern_prefix
                entry_extern_prefix = "" if _markers.OmitSubcommandPrefixes in field.markers else extern_prefix
                entry_subcommand_prefix = "" if _markers.OmitSubcommandPrefixes in field.markers else intern_prefix

            subcommand_entries.append(
                _SubcommandEntry(
                    name=subcommand_name,
                    config=config,
                    parser_type=parser_type,
                    type_for_matching=annotated_type,
                    uses_wrapper=uses_wrapper,
                    intern_prefix=entry_intern_prefix,
                    extern_prefix=entry_extern_prefix,
                    subcommand_prefix=entry_subcommand_prefix,
                )
            )

        default_candidate: Any = field.default
        if default_candidate in _singleton.MISSING_AND_MISSING_NONPROP:
            for union_config in union_level_configs:
                if union_config.default not in _singleton.MISSING_AND_MISSING_NONPROP:
                    default_candidate = union_config.default
                    break

        if default_candidate in _singleton.MISSING_AND_MISSING_NONPROP:
            for entry in subcommand_entries:
                config_default = entry.config.default
                if config_default not in _singleton.MISSING_AND_MISSING_NONPROP:
                    default_candidate = config_default
                    break

        default_name: str | None = None
        if default_candidate not in _singleton.MISSING_AND_MISSING_NONPROP:
            if default_candidate is None:
                default_name = next(
                    (
                        entry.name
                        for entry in subcommand_entries
                        if entry.parser_type is none_proxy
                    ),
                    None,
                )
            else:
                default_name = _subcommand_matching.match_subcommand(
                    default_candidate,
                    subcommand_config_from_name,
                    subcommand_type_from_name,
                )

            if default_name is None and field.default not in _singleton.MISSING_AND_MISSING_NONPROP:
                assert False, (
                    f"`{extern_prefix}` was provided a default value of type {type(field.default)}"
                    " but no matching subcommand was found."
                )

        if (
            default_name is not None
            and field.default not in _singleton.MISSING_AND_MISSING_NONPROP
        ):
            for i, entry in enumerate(subcommand_entries):
                if entry.name == default_name:
                    new_config = dataclasses.replace(
                        entry.config, default=field.default
                    )
                    subcommand_entries[i] = dataclasses.replace(entry, config=new_config)
                    subcommand_config_from_name[entry.name] = new_config
                    break

        if (
            default_name is not None
            and _markers.AvoidSubcommands in field.markers
            and field.default not in _singleton.MISSING_AND_MISSING_NONPROP
        ):
            return ParserSpecification.from_callable_or_type(
                cast(type, subcommand_type_from_name[default_name]),
                markers=field.markers,
                description=None,
                parent_classes=parent_classes,
                default_instance=default_candidate,
                intern_prefix=intern_prefix,
                extern_prefix=extern_prefix,
                add_help=add_help,
                subcommand_prefix=intern_prefix,
                support_single_arg_types=False,
            )

        parser_from_name: Dict[str, ParserSpecification] = {}
        options_for_spec: List[Union[type, Callable]] = []

        for entry in subcommand_entries:
            default_for_parser = entry.config.default
            if (
                default_for_parser not in _singleton.MISSING_AND_MISSING_NONPROP
                and entry.uses_wrapper
            ):
                default_for_parser = entry.parser_type(default_for_parser)  # type: ignore[arg-type]

            with _fields.FieldDefinition.marker_context(tuple(field.markers)):
                subparser = ParserSpecification.from_callable_or_type(
                    entry.parser_type,  # type: ignore[arg-type]
                    markers=field.markers,
                    description=entry.config.description,
                    parent_classes=parent_classes,
                    default_instance=default_for_parser,
                    intern_prefix=entry.intern_prefix,
                    extern_prefix=entry.extern_prefix,
                    add_help=add_help,
                    subcommand_prefix=entry.subcommand_prefix,
                    support_single_arg_types=True,
                )

            subparser = dataclasses.replace(
                subparser,
                helptext_from_intern_prefixed_field_name={
                    _strings.make_intern_prefix([intern_prefix, k]): v
                    for k, v in subparser.helptext_from_intern_prefixed_field_name.items()
                },
            )

            parser_from_name[entry.name] = subparser
            options_for_spec.append(entry.parser_type)

        if default_name is not None and default_name not in parser_from_name:
            default_name = None

        default_parser = None
        if default_name is None:
            required = True
        else:
            required = False
            default_parser = parser_from_name[default_name]
            if any(arg.lowered.required for arg in default_parser.args):
                required = True
                default_parser = None
            elif (
                default_parser.subparsers is not None
                and default_parser.subparsers.required
            ):
                required = True
                default_parser = None

        return SubparsersSpecification(
            name=field.intern_name,
            description=field.helptext,
            parser_from_name=parser_from_name,
            default_name=default_name,
            default_parser=default_parser,
            intern_prefix=intern_prefix,
            required=required,
            default_instance=default_candidate,
            options=tuple(options_for_spec),
        )

    def apply(
        self,
        parent_parser: argparse.ArgumentParser,
        force_required_subparsers: bool,
    ) -> Tuple[argparse.ArgumentParser, ...]:
        title = "subcommands"
        metavar = "{" + ",".join(self.parser_from_name.keys()) + "}"

        required = self.required or force_required_subparsers

        if not required:
            title = "optional " + title
            metavar = f"[{metavar}]"

        # Make description.
        description_parts = []
        if self.description is not None:
            description_parts.append(self.description)
        if not required and self.default_name is not None:
            description_parts.append(f"(default: {self.default_name})")

        # If this subparser is required because of a required argument in a
        # parent (tyro.conf.ConsolidateSubcommandArgs).
        if not self.required and force_required_subparsers:
            description_parts.append("(required to specify parent argument)")

        description = (
            # We use `None` instead of an empty string to prevent a line break from
            # being created where the description would be.
            " ".join(description_parts) if len(description_parts) > 0 else None
        )

        # Add subparsers to every node in previous level of the tree.
        argparse_subparsers = parent_parser.add_subparsers(
            dest=_strings.make_subparser_dest(self.intern_prefix),
            description=description,
            required=required,
            title=title,
            metavar=metavar,
        )

        subparser_tree_leaves: List[argparse.ArgumentParser] = []
        for name, subparser_def in self.parser_from_name.items():
            helptext = subparser_def.description.replace("%", "%%")
            if len(helptext) > 0:
                # TODO: calling a private function here.
                helptext = _arguments._rich_tag_if_enabled(helptext.strip(), "helptext")

            subparser = argparse_subparsers.add_parser(
                name,
                formatter_class=_argparse_formatter.TyroArgparseHelpFormatter,
                help=helptext,
                allow_abbrev=False,
                add_help=parent_parser.add_help,
            )

            # Attributes used for error message generation.
            assert isinstance(subparser, _argparse_formatter.TyroArgumentParser)
            assert isinstance(parent_parser, _argparse_formatter.TyroArgumentParser)
            subparser._parsing_known_args = parent_parser._parsing_known_args
            subparser._parser_specification = parent_parser._parser_specification
            subparser._console_outputs = parent_parser._console_outputs
            subparser._args = parent_parser._args

            subparser_tree_leaves.extend(
                subparser_def.apply(subparser, force_required_subparsers)
            )

        return tuple(subparser_tree_leaves)


def add_subparsers_to_leaves(
    root: SubparsersSpecification | None, leaf: SubparsersSpecification
) -> SubparsersSpecification:
    if root is None:
        return leaf

    new_parsers_from_name = {}
    for name, parser in root.parser_from_name.items():
        new_parsers_from_name[name] = dataclasses.replace(
            parser,
            subparsers=add_subparsers_to_leaves(parser.subparsers, leaf),
        )
    return dataclasses.replace(
        root,
        parser_from_name=new_parsers_from_name,
        required=root.required or leaf.required,
    )


def none_proxy() -> None:
    return None
