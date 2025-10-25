"""Interface for generating `argparse.ArgumentParser()` definitions from callables."""

from __future__ import annotations

import dataclasses
import numbers
import warnings
from typing import Any, Callable, Dict, List, Set, Tuple, Type, TypeVar, Union, cast

from typing_extensions import Annotated, get_args, get_origin

from tyro.constructors._registry import ConstructorRegistry
from tyro.constructors._struct_spec import UnsupportedStructTypeMessage

from . import (
    _arguments,
    _docstrings,
    _fields,
    _resolver,
    _singleton,
    _strings,
    _subcommand_matching,
)
from ._backends import _argparse as argparse
from ._backends import _argparse_formatter
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

    # Subparser groups that are direct children of this parser. The actual tree
    # structure for argparse is built on-demand in apply().
    subparsers_from_intern_prefix: Dict[str, SubparsersSpecification]
    intern_prefix: str
    extern_prefix: str
    has_required_args: bool
    subparser_parent: ParserSpecification | None
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
        is_root: bool,
        add_help: bool,
        subcommand_prefix: str,
        support_single_arg_types: bool,
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
            assert not isinstance(out, UnsupportedStructTypeMessage), out
            f, field_list = out

        has_required_args = False
        args = []
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
            add_help=add_help,
        )

        return parser_spec

    def get_args_including_children(self) -> list[_arguments.ArgumentDefinition]:
        """Get all arguments in this parser and its children.

        Does not include arguments in subparsers.
        """
        args = self.args.copy()
        for child in self.child_from_prefix.values():
            args.extend(child.get_args_including_children())
        return args

    def apply(
        self, parser: argparse.ArgumentParser, force_required_subparsers: bool
    ) -> Tuple[argparse.ArgumentParser, ...]:
        """Create defined arguments and subparsers."""
        from ._backends import _argparse_backend

        # Generate helptext.
        parser.description = self.description

        # `force_required_subparsers`: if we have required arguments and we're
        # consolidating all arguments into the leaves of the subparser trees, a
        # required argument in one node of this tree means that all of its
        # descendants are required.
        if (
            _markers.CascadingSubcommandArgs in self.markers
        ) and self.has_required_args:
            force_required_subparsers = True

        # Create subparser tree.
        # Build materialized tree from direct subparsers on-demand for argparse.
        subparser_group = None
        root_subparsers = _argparse_backend.build_parser_subparsers(self)

        if root_subparsers is not None:
            leaves = _argparse_backend.apply_materialized_subparsers(
                self,
                root_subparsers,
                parser,
                force_required_subparsers,
                force_consolidate_args=_markers.CascadingSubcommandArgs
                in self.markers,
            )
            subparser_group = parser._action_groups.pop()
        else:
            leaves = (parser,)

        # Depending on whether we want to cascade subcommand args, we can either
        # apply arguments to the intermediate parser or only on the leaves.
        if _markers.CascadingSubcommandArgs in self.markers:
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
            elif arg.is_positional():
                arg.add_argument(positional_group)
                continue
            elif arg.field.mutex_group is not None:
                group_conf = arg.field.mutex_group
                if group_conf not in exclusive_group_from_group_conf:
                    exclusive_group_from_group_conf[group_conf] = (
                        parser.add_mutually_exclusive_group(
                            required=group_conf.required
                        )
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
                add_help=add_help,
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
                add_help=add_help,
                subcommand_prefix=subcommand_prefix,
                support_single_arg_types=False,
                is_root=False,
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

        # We don't use sets here to retain order of subcommands.
        options: List[Union[type, Callable]]
        options = [typ for typ in get_args(typ)]

        # If specified, swap types using tyro.conf.subcommand(constructor=...).
        for i, option in enumerate(options):
            _, found_subcommand_configs = _resolver.unwrap_annotated(
                option, _confstruct._SubcommandConfig
            )
            if (
                len(found_subcommand_configs) > 0
                and found_subcommand_configs[0].constructor_factory is not None
            ):
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

        if not recursive_contains_struct_type(options):
            return None

        # Get subcommand configurations from `tyro.conf.subcommand()`.
        subcommand_config_from_name: Dict[str, _confstruct._SubcommandConfig] = {}
        subcommand_type_from_name: Dict[str, type] = {}
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
            if subcommand_name in subcommand_type_from_name:
                # Raise a warning that the subcommand already exists
                original_type = subcommand_type_from_name[subcommand_name]
                original_type_full_name = (
                    f"{original_type.__module__}.{original_type.__name__}"
                )
                new_type_full_name = (
                    f"{option_unwrapped.__module__}.{option_unwrapped.__name__}"
                    if option_unwrapped is not None
                    else "None"
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
        default_name = None
        if field.default not in _singleton.MISSING_AND_MISSING_NONPROP:
            default_name = _subcommand_matching.match_subcommand(
                field.default,
                subcommand_config_from_name,
                subcommand_type_from_name,
            )
            assert default_name is not None, (
                f"`{extern_prefix}` was provided a default value of type"
                f" {type(field.default)} but no matching subcommand was found. A"
                " type may be missing in the Union type declaration for"
                f" `{extern_prefix}`, which currently expects {options}. "
                "The types may also be too complex for tyro's subcommand matcher; support "
                "is particularly limited for custom generic types."
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
                is_root=False,
                add_help=add_help,
                subcommand_prefix=extern_prefix,
                support_single_arg_types=True,
            )

        # Add subcommands for each option.
        parser_from_name: Dict[str, ParserSpecification] = {}
        for option in options:
            subcommand_name = _strings.subparser_name_from_type(
                (
                    ""
                    if _markers.OmitSubcommandPrefixes in field.markers
                    else extern_prefix
                ),
                cast(type, option),
            )

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

            with _fields.FieldDefinition.marker_context(tuple(field.markers)):
                subparser = ParserSpecification.from_callable_or_type(
                    option,  # type: ignore
                    markers=field.markers,
                    description=subcommand_config.description,
                    parent_classes=parent_classes,
                    default_instance=subcommand_config.default,
                    intern_prefix=intern_prefix,
                    extern_prefix=extern_prefix,
                    is_root=False,
                    add_help=add_help,
                    subcommand_prefix=extern_prefix,
                    support_single_arg_types=True,
                )

            # Apply prefix to helptext in nested classes in subparsers.
            subparser = dataclasses.replace(
                subparser,
                helptext_from_intern_prefixed_field_name={
                    _strings.make_field_name([intern_prefix, k]): v
                    for k, v in subparser.helptext_from_intern_prefixed_field_name.items()
                },
            )
            parser_from_name[subcommand_name] = subparser

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
            default_parser = parser_from_name[default_name]

            # If there are any required arguments.
            if any(map(lambda arg: arg.lowered.required, default_parser.args)):
                required = True
                default_parser = None

            # If there are any required subparsers.
            elif any(
                subparser_spec.required
                for subparser_spec in default_parser.subparsers_from_intern_prefix.values()
            ):
                required = True
                default_parser = None

        return SubparsersSpecification(
            # If we wanted, we could add information about the default instance
            # automatically, as is done for normal fields. But for now we just rely on
            # the user to include it in the docstring.
            description=field.helptext,
            parser_from_name=parser_from_name,
            default_name=default_name,
            default_parser=default_parser,
            intern_prefix=intern_prefix,
            required=required,
            default_instance=field.default,
            options=tuple(options),
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
        # parent (tyro.conf.CascadingSubcommandArgs).
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
            subparser = argparse_subparsers.add_parser(
                name,
                help=helptext,
                allow_abbrev=False,
                add_help=parent_parser.add_help,
            )

            # Attributes used for error message generation.
            assert isinstance(subparser, _argparse_formatter.TyroArgumentParser)
            assert isinstance(parent_parser, _argparse_formatter.TyroArgumentParser)
            subparser._parsing_known_args = parent_parser._parsing_known_args
            subparser._parser_specification = subparser_def
            subparser._console_outputs = parent_parser._console_outputs
            subparser._args = parent_parser._args

            subparser_tree_leaves.extend(
                subparser_def.apply(subparser, force_required_subparsers)
            )

        return tuple(subparser_tree_leaves)
