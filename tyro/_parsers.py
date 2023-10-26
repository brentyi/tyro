"""Interface for generating `argparse.ArgumentParser()` definitions from callables."""

from __future__ import annotations

import argparse
import dataclasses
import warnings
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from typing_extensions import Annotated, get_args, get_origin

from . import (
    _argparse_formatter,
    _arguments,
    _docstrings,
    _fields,
    _instantiators,
    _resolver,
    _strings,
    _subcommand_matching,
)
from ._typing import TypeForm
from .conf import _confstruct, _markers

T = TypeVar("T")


@dataclasses.dataclass(frozen=True)
class ParserSpecification:
    """Each parser contains a list of arguments and optionally some subparsers."""

    f: Callable
    description: str
    args: List[_arguments.ArgumentDefinition]
    helptext_from_nested_class_field_name: Dict[str, Optional[str]]

    # We have two mechanics for tracking subparser groups:
    # - A single subparser group, which is what gets added in the tree structure built
    # by the argparse parser.
    subparsers: Optional[SubparsersSpecification]
    # - A set of subparser groups, which reflect the tree structure built by the
    # hierarchy of a nested config structure.
    subparsers_from_prefix: Dict[str, SubparsersSpecification]
    prefix: str
    has_required_args: bool
    consolidate_subcommand_args: bool

    @staticmethod
    def from_callable_or_type(
        f: Callable[..., T],
        description: Optional[str],
        parent_classes: Set[Type[Any]],
        default_instance: Union[
            T, _fields.PropagatingMissingType, _fields.NonpropagatingMissingType
        ],
        prefix: str,
        subcommand_prefix: str = "",
    ) -> ParserSpecification:
        """Create a parser definition from a callable or type."""

        # Consolidate subcommand types.
        consolidate_subcommand_args = (
            _markers.ConsolidateSubcommandArgs
            in _resolver.unwrap_annotated(f, _markers._Marker)[1]
        )

        # Resolve the type of `f`, generate a field list.
        f, type_from_typevar, field_list = _fields.field_list_from_callable(
            f=f, default_instance=default_instance
        )

        # Cycle detection.
        #
        # Note that 'parent' here refers to in the nesting hierarchy, not the
        # superclass.
        if f in parent_classes and f is not dict:
            raise _instantiators.UnsupportedTypeAnnotationError(
                f"Found a cyclic dataclass dependency with type {f}."
            )

        # TODO: we are abusing the (minor) distinctions between types, classes, and
        # callables throughout the code. This is mostly for legacy reasons, could be
        # cleaned up.
        parent_classes = parent_classes | {cast(Type, f)}

        has_required_args = False
        args = []
        helptext_from_nested_class_field_name: Dict[str, Optional[str]] = {}

        subparsers = None
        subparsers_from_prefix = {}

        for field in field_list:
            field_out = handle_field(
                field,
                type_from_typevar=type_from_typevar,
                parent_classes=parent_classes,
                prefix=prefix,
                subcommand_prefix=subcommand_prefix,
            )
            if isinstance(field_out, _arguments.ArgumentDefinition):
                # Handle single arguments.
                args.append(field_out)
                if field_out.lowered.required:
                    has_required_args = True
            elif isinstance(field_out, SubparsersSpecification):
                # Handle subparsers.
                subparsers_from_prefix[field_out.prefix] = field_out
                subparsers = add_subparsers_to_leaves(subparsers, field_out)
            elif isinstance(field_out, ParserSpecification):
                # Handle nested parsers.
                nested_parser = field_out

                if nested_parser.has_required_args:
                    has_required_args = True
                args.extend(nested_parser.args)

                # Include nested subparsers.
                if nested_parser.subparsers is not None:
                    subparsers_from_prefix.update(nested_parser.subparsers_from_prefix)
                    subparsers = add_subparsers_to_leaves(
                        subparsers, nested_parser.subparsers
                    )

                # Include nested strings.
                for (
                    k,
                    v,
                ) in nested_parser.helptext_from_nested_class_field_name.items():
                    helptext_from_nested_class_field_name[
                        _strings.make_field_name([field.name, k])
                    ] = v

                class_field_name = _strings.make_field_name([field.name])
                if field.helptext is not None:
                    helptext_from_nested_class_field_name[
                        class_field_name
                    ] = field.helptext
                else:
                    helptext_from_nested_class_field_name[
                        class_field_name
                    ] = _docstrings.get_callable_description(nested_parser.f)

                # If arguments are in an optional group, it indicates that the default_instance
                # will be used if none of the arguments are passed in.
                if (
                    len(nested_parser.args) >= 1
                    and _markers._OPTIONAL_GROUP in nested_parser.args[0].field.markers
                ):
                    current_helptext = helptext_from_nested_class_field_name[
                        class_field_name
                    ]
                    helptext_from_nested_class_field_name[class_field_name] = (
                        ("" if current_helptext is None else current_helptext + "\n\n")
                        + "Default: "
                        + str(field.default)
                    )

        return ParserSpecification(
            f=f,
            description=_strings.remove_single_line_breaks(
                description
                if description is not None
                else _docstrings.get_callable_description(f)
            ),
            args=args,
            helptext_from_nested_class_field_name=helptext_from_nested_class_field_name,
            subparsers=subparsers,
            subparsers_from_prefix=subparsers_from_prefix,
            prefix=prefix,
            has_required_args=has_required_args,
            consolidate_subcommand_args=consolidate_subcommand_args,
        )

    def apply(
        self, parser: argparse.ArgumentParser
    ) -> Tuple[argparse.ArgumentParser, ...]:
        """Create defined arguments and subparsers."""

        # Generate helptext.
        parser.description = self.description

        # Create subparser tree.
        subparser_group = None
        if self.subparsers is not None:
            leaves = self.subparsers.apply(parser)
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

        # Break some API boundaries to rename the "optional arguments" => "arguments".
        assert parser._action_groups[1].title in (
            # python <= 3.9
            "optional arguments",
            # python >= 3.10
            "options",
        )
        parser._action_groups[1].title = "arguments"

        return leaves

    def apply_args(self, parser: argparse.ArgumentParser) -> None:
        """Create defined arguments and subparsers."""

        # Generate helptext.
        parser.description = self.description

        # Make argument groups.
        def format_group_name(prefix: str) -> str:
            return (prefix + " arguments").strip()

        group_from_prefix: Dict[str, argparse._ArgumentGroup] = {
            "": parser._action_groups[1],
            **{
                cast(str, group.title).partition(" ")[0]: group
                for group in parser._action_groups[2:]
            },
        }
        positional_group = parser._action_groups[0]
        assert positional_group.title == "positional arguments"

        # Add each argument group. Note that groups with only suppressed arguments won't
        # be added.
        for arg in self.args:
            if (
                arg.lowered.help is not argparse.SUPPRESS
                and arg.dest_prefix not in group_from_prefix
            ):
                description = self.helptext_from_nested_class_field_name.get(
                    arg.dest_prefix
                )
                group_from_prefix[arg.dest_prefix] = parser.add_argument_group(
                    format_group_name(arg.dest_prefix),
                    description=description,
                )

        # Add each argument.
        for arg in self.args:
            if arg.field.is_positional():
                arg.add_argument(positional_group)
                continue

            if arg.dest_prefix in group_from_prefix:
                arg.add_argument(group_from_prefix[arg.dest_prefix])
            else:
                # Suppressed argument: still need to add them, but they won't show up in
                # the helptext so it doesn't matter which group.
                assert arg.lowered.help is argparse.SUPPRESS
                arg.add_argument(group_from_prefix[""])


def handle_field(
    field: _fields.FieldDefinition,
    type_from_typevar: Dict[TypeVar, TypeForm[Any]],
    parent_classes: Set[Type[Any]],
    prefix: str,
    subcommand_prefix: str,
) -> Union[
    _arguments.ArgumentDefinition,
    ParserSpecification,
    SubparsersSpecification,
]:
    """Determine what to do with a single field definition."""

    if isinstance(field.type_or_callable, TypeVar):
        raise _instantiators.UnsupportedTypeAnnotationError(
            f"Field {field.name} has an unbound TypeVar: {field.type_or_callable}."
        )

    if _markers.Fixed not in field.markers:
        # (1) Handle Unions over callables; these result in subparsers.
        subparsers_attempt = SubparsersSpecification.from_field(
            field,
            type_from_typevar=type_from_typevar,
            parent_classes=parent_classes,
            prefix=_strings.make_field_name([prefix, field.name]),
        )
        if subparsers_attempt is not None:
            if (
                not subparsers_attempt.required
                and _markers.AvoidSubcommands in field.markers
            ):
                # Don't make a subparser.
                field = dataclasses.replace(field, type_or_callable=type(field.default))
            else:
                return subparsers_attempt

        # (2) Handle nested callables.
        if _fields.is_nested_type(field.type_or_callable, field.default):
            field = dataclasses.replace(
                field,
                type_or_callable=_resolver.narrow_type(
                    field.type_or_callable,
                    field.default,
                ),
            )
            return ParserSpecification.from_callable_or_type(
                (
                    # Recursively apply marker types.
                    field.type_or_callable
                    if len(field.markers) == 0
                    else Annotated.__class_getitem__(  # type: ignore
                        (field.type_or_callable,) + tuple(field.markers)
                    )
                ),
                description=None,
                parent_classes=parent_classes,
                default_instance=field.default,
                prefix=_strings.make_field_name([prefix, field.name]),
                subcommand_prefix=subcommand_prefix,
            )

    # (3) Handle primitive or fixed types. These produce a single argument!
    return _arguments.ArgumentDefinition(
        dest_prefix=prefix,
        name_prefix=prefix,
        subcommand_prefix=subcommand_prefix,
        field=field,
        type_from_typevar=type_from_typevar,
    )


@dataclasses.dataclass(frozen=True)
class SubparsersSpecification:
    """Structure for defining subparsers. Each subparser is a parser with a name."""

    name: str
    description: Optional[str]
    parser_from_name: Dict[str, ParserSpecification]
    prefix: str
    required: bool
    default_instance: Any
    options: Tuple[Union[TypeForm[Any], Callable], ...]

    @staticmethod
    def from_field(
        field: _fields.FieldDefinition,
        type_from_typevar: Dict[TypeVar, TypeForm[Any]],
        parent_classes: Set[Type[Any]],
        prefix: str,
    ) -> Optional[SubparsersSpecification]:
        # Union of classes should create subparsers.
        typ = _resolver.unwrap_annotated(field.type_or_callable)[0]
        if get_origin(typ) is not Union:
            return None

        # We don't use sets here to retain order of subcommands.
        options: List[Union[type, Callable]]
        options = [
            _resolver.apply_type_from_typevar(typ, type_from_typevar)
            for typ in get_args(typ)
        ]
        options = [
            (
                # Cast seems unnecessary but needed in mypy... (1.4.1)
                cast(Callable, none_proxy)
                if o is type(None)
                else o
            )
            for o in options
        ]

        # If specified, swap types using tyro.conf.subcommand(constructor=...).
        for i, option in enumerate(options):
            _, found_subcommand_configs = _resolver.unwrap_annotated(
                option, _confstruct._SubcommandConfiguration
            )
            if (
                len(found_subcommand_configs) > 0
                and found_subcommand_configs[0].constructor_factory is not None
            ):
                options[i] = found_subcommand_configs[0].constructor_factory()

        # Exit if we don't contain nested types.
        if not all(
            [
                _fields.is_nested_type(cast(type, o), _fields.MISSING_NONPROP)
                for o in options
            ]
        ):
            return None

        # Get subcommand configurations from `tyro.conf.subcommand()`.
        subcommand_config_from_name: Dict[
            str, _confstruct._SubcommandConfiguration
        ] = {}
        subcommand_type_from_name: Dict[str, type] = {}
        for option in options:
            subcommand_name = _strings.subparser_name_from_type(
                prefix, type(None) if option is none_proxy else cast(type, option)
            )
            option, found_subcommand_configs = _resolver.unwrap_annotated(
                option, _confstruct._SubcommandConfiguration
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
        if field.default is None or field.default in _fields.MISSING_SINGLETONS:
            default_name = None
        else:
            default_name = _subcommand_matching.match_subcommand(
                field.default, subcommand_config_from_name, subcommand_type_from_name
            )
            if default_name is None:
                # This should really be an error, but we can raise a warning to make
                # hacking at subcommands easier:
                # https://github.com/brentyi/tyro/issues/20
                warnings.warn(
                    f"`{prefix}` was provided a default value of type"
                    f" {type(field.default)} but no matching subcommand was found. A"
                    " type may be missing in the Union type declaration for"
                    f" `{prefix}`, which currently expects {options}."
                )
                return None

        # Add subcommands for each option.
        parser_from_name: Dict[str, ParserSpecification] = {}
        for option in options:
            subcommand_name = _strings.subparser_name_from_type(
                prefix, type(None) if option is none_proxy else cast(type, option)
            )
            option, _ = _resolver.unwrap_annotated(option)

            # Get a subcommand config: either pulled from the type annotations or the
            # field default.
            if subcommand_name in subcommand_config_from_name:
                subcommand_config = subcommand_config_from_name[subcommand_name]
            else:
                subcommand_config = _confstruct._SubcommandConfiguration(
                    "unused",
                    description=None,
                    default=_fields.MISSING_NONPROP,
                    prefix_name=True,
                    constructor_factory=None,
                )

            # If names match, borrow subcommand default from field default.
            if default_name == subcommand_name:
                subcommand_config = dataclasses.replace(
                    subcommand_config, default=field.default
                )
            subparser = ParserSpecification.from_callable_or_type(
                (
                    # Recursively apply markers.
                    Annotated.__class_getitem__((option,) + tuple(field.markers))  # type: ignore
                    if len(field.markers) > 0
                    else option
                ),
                description=subcommand_config.description,
                parent_classes=parent_classes,
                default_instance=subcommand_config.default,
                prefix=prefix,
                subcommand_prefix=prefix,
            )

            # Apply prefix to helptext in nested classes in subparsers.
            subparser = dataclasses.replace(
                subparser,
                helptext_from_nested_class_field_name={
                    _strings.make_field_name([prefix, k]): v
                    for k, v in subparser.helptext_from_nested_class_field_name.items()
                },
            )
            parser_from_name[subcommand_name] = subparser

        # Required if a default is missing.
        required = field.default in _fields.MISSING_SINGLETONS

        # Required if a default is passed in, but the default value has missing
        # parameters.
        if default_name is not None:
            default_parser = parser_from_name[default_name]
            if any(map(lambda arg: arg.lowered.required, default_parser.args)):
                required = True
            if (
                default_parser.subparsers is not None
                and default_parser.subparsers.required
            ):
                required = True

        # Required if all args are pushed to the final subcommand.
        if _markers.ConsolidateSubcommandArgs in field.markers:
            required = True

        # Make description.
        description_parts = []
        if field.helptext is not None:
            description_parts.append(field.helptext)
        if not required and field.default not in _fields.MISSING_SINGLETONS:
            description_parts.append(f" (default: {default_name})")
        description = (
            # We use `None` instead of an empty string to prevent a line break from
            # being created where the description would be.
            " ".join(description_parts)
            if len(description_parts) > 0
            else None
        )

        return SubparsersSpecification(
            name=field.name,
            # If we wanted, we could add information about the default instance
            # automatically, as is done for normal fields. But for now we just rely on
            # the user to include it in the docstring.
            description=description,
            parser_from_name=parser_from_name,
            prefix=prefix,
            required=required,
            default_instance=field.default,
            options=tuple(options),
        )

    def apply(
        self, parent_parser: argparse.ArgumentParser
    ) -> Tuple[argparse.ArgumentParser, ...]:
        title = "subcommands"
        metavar = "{" + ",".join(self.parser_from_name.keys()) + "}"
        if not self.required:
            title = "optional " + title
            metavar = f"[{metavar}]"

        # Add subparsers to every node in previous level of the tree.
        argparse_subparsers = parent_parser.add_subparsers(
            dest=_strings.make_subparser_dest(self.prefix),
            description=self.description,
            required=self.required,
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
            )

            # Attributes used for error message generation.
            assert isinstance(subparser, _argparse_formatter.TyroArgumentParser)
            assert isinstance(parent_parser, _argparse_formatter.TyroArgumentParser)
            subparser._parsing_known_args = parent_parser._parsing_known_args
            subparser._parser_specification = parent_parser._parser_specification
            subparser._args = parent_parser._args

            subparser_tree_leaves.extend(subparser_def.apply(subparser))

        return tuple(subparser_tree_leaves)


def add_subparsers_to_leaves(
    root: Optional[SubparsersSpecification], leaf: SubparsersSpecification
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
