"""Interface for generating `argparse.ArgumentParser()` definitions from callables."""

from __future__ import annotations

import argparse
import dataclasses
import itertools
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar, Union, cast

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
from .conf import _markers, _subcommands

T = TypeVar("T")


@dataclasses.dataclass(frozen=True)
class ParserSpecification:
    """Each parser contains a list of arguments and optionally some subparsers."""

    f: Callable
    description: str
    args: List[_arguments.ArgumentDefinition]
    helptext_from_nested_class_field_name: Dict[str, Optional[str]]
    subparsers_from_name: Dict[str, SubparsersSpecification]
    prefix: str
    has_required_args: bool

    @staticmethod
    def from_callable_or_type(
        f: Callable[..., T],
        description: Optional[str],
        parent_classes: Set[Type],
        parent_type_from_typevar: Optional[Dict[TypeVar, Type]],
        default_instance: Union[
            T, _fields.PropagatingMissingType, _fields.NonpropagatingMissingType
        ],
        prefix: str,
        subcommand_prefix: str = "",
    ) -> ParserSpecification:
        """Create a parser definition from a callable or type."""

        # Resolve generic types.
        f, type_from_typevar = _resolver.resolve_generic_types(f)
        f = _resolver.narrow_type(f, default_instance)
        if parent_type_from_typevar is not None:
            for typevar, typ in type_from_typevar.items():
                if typ in parent_type_from_typevar:
                    type_from_typevar[typevar] = parent_type_from_typevar[typ]  # type: ignore

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
        subparsers_from_name = {}

        field_list = _fields.field_list_from_callable(
            f=f, default_instance=default_instance
        )
        for field in field_list:
            field = dataclasses.replace(
                field,
                # Resolve generic types.
                typ=_resolver.type_from_typevar_constraints(
                    _resolver.apply_type_from_typevar(
                        field.typ,
                        type_from_typevar,
                    )
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
                        subparsers_from_name[
                            _strings.make_field_name([prefix, subparsers_attempt.name])
                        ] = subparsers_attempt
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
                        field.typ,
                        description=None,
                        parent_classes=parent_classes,
                        parent_type_from_typevar=type_from_typevar,
                        default_instance=field.default,
                        prefix=_strings.make_field_name([prefix, field.name]),
                        subcommand_prefix=subcommand_prefix,
                    )
                    if nested_parser.has_required_args:
                        has_required_args = True
                    args.extend(nested_parser.args)

                    # Include nested subparsers.
                    subparsers_from_name.update(nested_parser.subparsers_from_name)

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

        # If a later subparser is required, all previous ones should be as well.
        subparsers_required = False
        for name, subparsers in list(subparsers_from_name.items())[::-1]:
            if subparsers.required:
                subparsers_required = True
            subparsers_from_name[name] = dataclasses.replace(
                subparsers, required=subparsers_required
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
            subparsers_from_name=subparsers_from_name,
            prefix=prefix,
            has_required_args=has_required_args,
        )

    def apply(self, parser: argparse.ArgumentParser) -> None:
        """Create defined arguments and subparsers."""

        # Generate helptext.
        parser.description = self.description

        # Make argument groups.
        def format_group_name(nested_field_name: str) -> str:
            return (nested_field_name + " arguments").strip()

        group_from_prefix: Dict[str, argparse._ArgumentGroup] = {
            "": parser._action_groups[1],
        }

        # Break some API boundaries to rename the optional group.
        parser._action_groups[1].title = format_group_name("")
        positional_group = parser.add_argument_group("positional arguments")
        parser._action_groups = parser._action_groups[::-1]

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

        # Create subparser tree.
        if len(self.subparsers_from_name) > 0:
            prev_subparser_tree_nodes = [parser]  # Root node.
            for subparsers in self.subparsers_from_name.values():
                prev_subparser_tree_nodes = subparsers.apply(
                    self, prev_subparser_tree_nodes
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
        options_no_none = [o for o in options if o != type(None)]  # noqa
        if not all(
            [
                _fields.is_nested_type(o, _fields.MISSING_NONPROP)
                for o in options_no_none
            ]
        ):
            return None

        # Get subcommand configurations from `tyro.conf.subcommand()`.
        subcommand_config_from_name: Dict[
            str, _subcommands._SubcommandConfiguration
        ] = {}
        subcommand_name_from_default_hash: Dict[int, str] = {}
        subcommand_name_from_type: Dict[Type, str] = {}  # Used for default matching.
        for option in options_no_none:
            subcommand_name = _strings.subparser_name_from_type(prefix, option)
            option, found_subcommand_configs = _resolver.unwrap_annotated(
                option, _subcommands._SubcommandConfiguration
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

            assert default_name is not None

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
                subcommand_config = _subcommands._SubcommandConfiguration(
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
                parent_type_from_typevar=type_from_typevar,
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
            if any(
                map(
                    lambda subparsers: subparsers.required,
                    default_parser.subparsers_from_name.values(),
                )
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
            # if field.default not in _fields.MISSING_SINGLETONS
            # else None,
            can_be_none=options != options_no_none,
        )

    def apply(
        self,
        parent_parser: ParserSpecification,
        prev_subparser_tree_nodes: List[argparse.ArgumentParser],
    ) -> List[argparse.ArgumentParser]:
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

        subparser_tree_nodes: List[argparse.ArgumentParser] = []
        for p in prev_subparser_tree_nodes:
            # Add subparsers to every node in previous level of the tree.
            argparse_subparsers = p.add_subparsers(
                dest=_strings.make_subparser_dest(self.prefix),
                description=self.description,
                required=self.required,
                title=title,
                metavar=metavar,
            )

            if self.can_be_none:
                subparser = argparse_subparsers.add_parser(
                    name=_strings.subparser_name_from_type(self.prefix, None),
                    formatter_class=_argparse_formatter.DcargsArgparseHelpFormatter,
                    help="",
                )
                subparser_tree_nodes.append(subparser)

            for name, subparser_def in self.parser_from_name.items():
                helptext = subparser_def.description.replace("%", "%%")
                if len(helptext) > 0:
                    # TODO: calling a private function here.
                    helptext = _arguments._rich_tag_if_enabled(
                        helptext.strip(), "helptext"
                    )

                subparser = argparse_subparsers.add_parser(
                    name,
                    formatter_class=_argparse_formatter.DcargsArgparseHelpFormatter,
                    help=helptext,
                )
                subparser_def.apply(subparser)

                def _get_leaf_subparsers(
                    node: argparse.ArgumentParser,
                ) -> List[argparse.ArgumentParser]:
                    if node._subparsers is None:
                        return [node]
                    else:
                        # Magic!
                        return list(
                            itertools.chain(
                                *map(
                                    _get_leaf_subparsers,
                                    node._subparsers._actions[
                                        -1
                                    ]._name_parser_map.values(),  # type: ignore
                                )
                            )
                        )

                subparser_tree_nodes.extend(_get_leaf_subparsers(subparser))

        return subparser_tree_nodes
