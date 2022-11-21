"""Interface for generating `argparse.ArgumentParser()` definitions from callables."""

from __future__ import annotations

import argparse
import dataclasses
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
)
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
        parent_classes: Set[Type],
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
            in _resolver.unwrap_annotated(f, _markers.Marker)[1]
        )

        # Resolve generic types.
        f, type_from_typevar = _resolver.resolve_generic_types(f)
        f = _resolver.narrow_type(f, default_instance)

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
        helptext_from_nested_class_field_name = {}

        subparsers = None
        subparsers_from_prefix = {}

        field_list = _fields.field_list_from_callable(
            f=f, default_instance=default_instance
        )
        for field in field_list:
            field = dataclasses.replace(
                field,
                # Resolve generic types.
                typ=_resolver.narrow_container_types(
                    _resolver.type_from_typevar_constraints(  # type: ignore
                        _resolver.apply_type_from_typevar(
                            field.typ,
                            type_from_typevar,
                        )
                    ),
                    default_instance=field.default,
                ),
            )

            if isinstance(field.typ, TypeVar):
                raise _instantiators.UnsupportedTypeAnnotationError(
                    f"Field {field.name} has an unbound TypeVar: {field.typ}."
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
                    if subparsers_attempt.required:
                        has_required_args = True
                    if (
                        not subparsers_attempt.required
                        and _markers.AvoidSubcommands in field.markers
                    ):
                        # Don't make a subparser.
                        field = dataclasses.replace(field, typ=type(field.default))
                    else:
                        subparsers_from_prefix[
                            subparsers_attempt.prefix
                        ] = subparsers_attempt
                        subparsers = add_subparsers_to_leaves(
                            subparsers, subparsers_attempt
                        )
                        continue

                # (2) Handle nested callables.
                if _fields.is_nested_type(field.typ, field.default):
                    field = dataclasses.replace(
                        field,
                        typ=_resolver.narrow_type(
                            field.typ,
                            field.default,
                        ),
                    )
                    nested_parser = ParserSpecification.from_callable_or_type(
                        # Recursively apply marker types.
                        field.typ
                        if len(field.markers) == 0
                        else Annotated.__class_getitem__(  # type: ignore
                            (field.typ,) + tuple(field.markers)
                        ),
                        description=None,
                        parent_classes=parent_classes,
                        default_instance=field.default,
                        prefix=_strings.make_field_name([prefix, field.name]),
                        subcommand_prefix=subcommand_prefix,
                    )
                    if nested_parser.has_required_args:
                        has_required_args = True
                    args.extend(nested_parser.args)

                    # Include nested subparsers.
                    if nested_parser.subparsers is not None:
                        subparsers_from_prefix[
                            nested_parser.subparsers.prefix
                        ] = nested_parser.subparsers
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

                    if field.helptext is not None:
                        helptext_from_nested_class_field_name[
                            _strings.make_field_name([field.name])
                        ] = field.helptext
                    else:
                        helptext_from_nested_class_field_name[
                            _strings.make_field_name([field.name])
                        ] = _docstrings.get_callable_description(field.typ)
                    continue

            # (3) Handle primitive or fixed types. These produce a single argument!
            arg = _arguments.ArgumentDefinition(
                prefix=prefix,
                subcommand_prefix=subcommand_prefix,
                field=field,
                type_from_typevar=type_from_typevar,
            )
            args.append(arg)
            if arg.lowered.required:
                has_required_args = True

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
                and arg.prefix not in group_from_prefix
            ):
                description = self.helptext_from_nested_class_field_name.get(arg.prefix)
                group_from_prefix[arg.prefix] = parser.add_argument_group(
                    format_group_name(arg.prefix),
                    description=description,
                )

        # Add each argument.
        for arg in self.args:
            if arg.field.is_positional():
                arg.add_argument(positional_group)
                continue

            if arg.prefix in group_from_prefix:
                arg.add_argument(group_from_prefix[arg.prefix])
            else:
                # Suppressed argument: still need to add them, but they won't show up in
                # the helptext so it doesn't matter which group.
                assert arg.lowered.help is argparse.SUPPRESS
                arg.add_argument(group_from_prefix[""])


@dataclasses.dataclass(frozen=True)
class SubparsersSpecification:
    """Structure for defining subparsers. Each subparser is a parser with a name."""

    name: str
    description: Optional[str]
    parser_from_name: Dict[str, ParserSpecification]
    prefix: str
    required: bool
    default_instance: Any
    can_be_none: bool  # If underlying type is Optional[Something].

    @staticmethod
    def from_field(
        field: _fields.FieldDefinition,
        type_from_typevar: Dict[TypeVar, Type],
        parent_classes: Set[Type],
        prefix: str,
    ) -> Optional[SubparsersSpecification]:
        # Union of classes should create subparsers.
        typ = _resolver.unwrap_annotated(field.typ)[0]
        if get_origin(typ) is not Union:
            return None

        # We don't use sets here to retain order of subcommands.
        options = [
            _resolver.apply_type_from_typevar(typ, type_from_typevar)
            for typ in get_args(typ)
        ]
        options_no_none = [o for o in options if o is not type(None)]  # noqa
        if not all(
            [
                _fields.is_nested_type(o, _fields.MISSING_NONPROP)
                for o in options_no_none
            ]
        ):
            return None

        # Get subcommand configurations from `tyro.conf.subcommand()`.
        subcommand_config_from_name: Dict[
            str, _confstruct._SubcommandConfiguration
        ] = {}
        subcommand_name_from_default_hash: Dict[int, str] = {}
        subcommand_name_from_type: Dict[Type, str] = {}  # Used for default matching.
        for option in options_no_none:
            subcommand_name = _strings.subparser_name_from_type(prefix, option)
            option, found_subcommand_configs = _resolver.unwrap_annotated(
                option, _confstruct._SubcommandConfiguration
            )
            default_hash = None
            if len(found_subcommand_configs) != 0:
                # Explicitly annotated default.
                assert len(found_subcommand_configs) == 1, (
                    f"Expected only one subcommand config, but {subcommand_name} has"
                    f" {len(found_subcommand_configs)}."
                )
                subcommand_config_from_name[subcommand_name] = found_subcommand_configs[
                    0
                ]

                if (
                    found_subcommand_configs[0].default
                    not in _fields.MISSING_SINGLETONS
                ):
                    default_hash = object.__hash__(found_subcommand_configs[0].default)
                    subcommand_name_from_default_hash[default_hash] = subcommand_name

            # Use subcommand types for default matching if no default is explicitly
            # annotated.
            if default_hash is None:
                subcommand_name_from_type[option] = subcommand_name

        # If there are any required arguments in the default subparser, we should mark
        # the subparser group as a whole as required.
        default_name = None
        if (
            field.default is not None
            and field.default not in _fields.MISSING_SINGLETONS
        ):
            # It's really hard to concretize a generic type at runtime, so we just...
            # don't. :-)
            if hasattr(type(field.default), "__parameters__"):
                raise _instantiators.UnsupportedTypeAnnotationError(
                    "Default values for generic subparsers are not supported."
                )

            # Get default subcommand name: by default hash.
            default_hash = object.__hash__(field.default)
            default_name = subcommand_name_from_default_hash.get(default_hash, None)

            # Get default subcommand name: by default value.
            if default_name is None:
                for (
                    subcommand_name,
                    subcommand_config,
                ) in subcommand_config_from_name.items():
                    equal = field.default == subcommand_config.default
                    if isinstance(equal, bool) and equal:
                        default_name = subcommand_name
                        break

            # Get default subcommand name: by default type.
            if default_name is None:
                default_name = subcommand_name_from_type.get(type(field.default), None)

            if default_name is None:
                raise AssertionError(
                    f"`{prefix}` was provided a default value of type"
                    f" {type(field.default)} but no matching subcommand was found. A"
                    " type may be missing in the Union type declaration for"
                    f" `{prefix}`, which is currently set to {field.typ}."
                )

        # Add subcommands for each option.
        parser_from_name: Dict[str, ParserSpecification] = {}
        for option in options_no_none:
            subcommand_name = _strings.subparser_name_from_type(prefix, option)
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
                )

            # If names match, borrow subcommand default from field default.
            if default_name == subcommand_name:
                subcommand_config = dataclasses.replace(
                    subcommand_config, default=field.default
                )
            subparser = ParserSpecification.from_callable_or_type(
                # Recursively apply markers.
                Annotated.__class_getitem__((option,) + tuple(field.markers))  # type: ignore
                if len(field.markers) > 0
                else option,
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
            can_be_none=options != options_no_none,
        )

    def apply(
        self, parent_parser: argparse.ArgumentParser
    ) -> Tuple[argparse.ArgumentParser, ...]:
        title = "subcommands"
        metavar = (
            "{"
            + ",".join(
                (
                    (_strings.subparser_name_from_type(self.prefix, None),)
                    if self.can_be_none
                    else ()
                )
                + tuple(self.parser_from_name.keys())
            )
            + "}"
        )
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

        if self.can_be_none:
            subparser = argparse_subparsers.add_parser(
                name=_strings.subparser_name_from_type(self.prefix, None),
                formatter_class=_argparse_formatter.TyroArgparseHelpFormatter,
                help="",
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
            )
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
