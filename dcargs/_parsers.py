"""Abstractions for creating argparse parsers from a dataclass definition."""

from __future__ import annotations

import argparse
import collections.abc
import dataclasses
import inspect
import itertools
from typing import (
    Any,
    Callable,
    Dict,
    Hashable,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
    cast,
)

import termcolor
import typing_extensions
from typing_extensions import get_args, get_origin, is_typeddict

from . import _arguments, _docstrings, _fields, _instantiators, _resolver, _strings

T = TypeVar("T")


_known_parsable_types = set(
    filter(
        lambda x: isinstance(x, Hashable),  # type: ignore
        itertools.chain(
            __builtins__.values(),  # type: ignore
            vars(typing_extensions).values(),
            vars(collections.abc).values(),
        ),
    )
)


def _is_possibly_nested_type(typ: Any) -> bool:
    """Heuristics for determining whether a type can be treated as a 'nested type',
    where a single field has multiple corresponding argumentsi (eg for nested
    dataclasses or classes).

    Examples of when we return False: int, str, List[int], List[str], pathlib.Path, etc.
    """

    typ = _resolver.unwrap_origin(typ)

    # Nested types should be callable.
    if not callable(typ):
        return False

    # Known parsable types: builtins like int/str/float/bool, collections, annotations.
    if typ in _known_parsable_types:
        return False

    # Simple heuristic: dataclasses should be treated as nested objects and are not
    # parsable.
    if dataclasses.is_dataclass(typ):
        return True

    # TypedDict types can be unpacked.
    if is_typeddict(typ):
        return True

    # Nested types like nested (data)classes should have fully type-annotated inputs. If
    # any inputs are unannotated (for example, in the case of pathlib.Path), we can
    # assume the type is not nested.
    for param in inspect.signature(typ).parameters.values():
        if param.annotation is inspect.Parameter.empty:
            return False

    return True


@dataclasses.dataclass(frozen=True)
class ParserSpecification:
    """Each parser contains a list of arguments and optionally some subparsers."""

    description: str
    args: List[_arguments.ArgumentDefinition]
    helptext_from_nested_class_field_name: Dict[str, Optional[str]]
    subparsers_from_name: Dict[str, SubparsersSpecification]
    prefix: str

    @staticmethod
    def from_callable(
        f: Callable[..., T],
        description: Optional[str],
        parent_classes: Set[Type],
        parent_type_from_typevar: Optional[Dict[TypeVar, Type]],
        default_instance: Optional[T],
        prefix: str,
        avoid_subparsers: bool,
    ) -> ParserSpecification:
        """Create a parser definition from a callable."""

        # Resolve generic types.
        f, type_from_typevar = _resolver.resolve_generic_types(f)
        if parent_type_from_typevar is not None:
            for typevar, typ in type_from_typevar.items():
                if typ in parent_type_from_typevar:
                    type_from_typevar[typevar] = parent_type_from_typevar[typ]  # type: ignore

        # Cycle detection.
        #
        # Note that 'parent' here refers to in the nesting hierarchy, not the
        # superclass.
        if f in parent_classes:
            raise _instantiators.UnsupportedTypeAnnotationError(
                f"Found a cyclic dataclass dependency with type {f}."
            )

        # TODO: we are abusing the (minor) distinctions between types, classes, and
        # callables throughout the code. This is mostly for legacy reasons, could be
        # cleaned up.
        parent_classes = parent_classes | {cast(Type, f)}

        args = []
        helptext_from_nested_class_field_name = {}
        subparsers_from_name = {}

        for field in _fields.field_list_from_callable(
            f=f, default_instance=default_instance
        ):
            field = dataclasses.replace(
                field,
                typ=type_from_typevar.get(field.typ, field.typ),  # type: ignore
            )
            if isinstance(field.typ, TypeVar):
                # Found an unbound TypeVar. This could be because inheriting from
                # generics is currently not implemented. It's unclear whether this is
                # feasible, because generics are lost in the mro:
                # https://github.com/python/typing/issues/777
                raise _instantiators.UnsupportedTypeAnnotationError(
                    f"Field {field.name} has an unbound TypeVar: {field.typ}. Note that"
                    " inheriting from generics is currently not implemented. It's"
                    " unclear whether this is feasible, because generics are lost in"
                    " the mro: https://github.com/python/typing/issues/777"
                )

            # (1) Handle Unions over callables; these result in subparsers.
            subparsers_attempt = SubparsersSpecification.from_field(
                field,
                type_from_typevar=type_from_typevar,
                parent_classes=parent_classes,
                prefix=prefix + field.name + _strings.NESTED_FIELD_DELIMETER,
                avoid_subparsers=avoid_subparsers,
            )
            if subparsers_attempt is not None:
                if (
                    not avoid_subparsers
                    # Required subparsers => must create a subparser.
                    or subparsers_attempt.required
                    # If the output can be None, the only way to specify whether this is
                    # or isn't None is with a subparser.
                    or subparsers_attempt.can_be_none
                ):
                    subparsers_from_name[subparsers_attempt.name] = subparsers_attempt
                    continue
                else:
                    field = dataclasses.replace(field, typ=type(field.default))
                    assert _is_possibly_nested_type(field.typ)

            # (2) Handle nested callables.
            if _is_possibly_nested_type(field.typ):
                nested_parser = ParserSpecification.from_callable(
                    field.typ,
                    description=None,
                    parent_classes=parent_classes,
                    parent_type_from_typevar=type_from_typevar,
                    default_instance=field.default,
                    prefix=prefix + field.name + _strings.NESTED_FIELD_DELIMETER,
                    avoid_subparsers=avoid_subparsers,
                )
                args.extend(nested_parser.args)

                for k, v in nested_parser.helptext_from_nested_class_field_name.items():
                    helptext_from_nested_class_field_name[
                        field.name + _strings.NESTED_FIELD_DELIMETER + k
                    ] = v

                if field.helptext is not None:
                    helptext_from_nested_class_field_name[field.name] = field.helptext
                else:
                    helptext_from_nested_class_field_name[
                        field.name
                    ] = _docstrings.get_callable_description(
                        _resolver.resolve_generic_types(field.typ)[0]
                    )
                continue

            # (3) Handle primitive types. These produce a single argument!
            args.append(
                _arguments.ArgumentDefinition(
                    prefix=prefix, field=field, type_from_typevar=type_from_typevar
                )
            )

        # If a later subparser is required, all previous ones should be as well.
        subparsers_required = False
        for name, subparsers in list(subparsers_from_name.items())[::-1]:
            if subparsers.required:
                subparsers_required = True
            subparsers_from_name[name] = dataclasses.replace(
                subparsers, required=subparsers_required
            )

        return ParserSpecification(
            description=description
            if description is not None
            else _docstrings.get_callable_description(f),
            args=args,
            helptext_from_nested_class_field_name=helptext_from_nested_class_field_name,
            subparsers_from_name=subparsers_from_name,
            prefix=prefix,
        )

    def apply(self, parser: argparse.ArgumentParser) -> None:
        """Create defined arguments and subparsers."""

        parser.description = self.description

        def format_group_name(nested_field_name: str, required: bool) -> str:
            if required:
                prefix = termcolor.colored("required", attrs=["bold"])
            else:
                prefix = termcolor.colored("optional", attrs=["bold", "dark"])
            suffix = termcolor.colored("arguments", attrs=["bold"])

            if nested_field_name != "":
                return " ".join(
                    [
                        prefix,
                        termcolor.colored(nested_field_name, attrs=["bold"]),
                        suffix,
                    ]
                )
            else:
                return " ".join([prefix, suffix])

        optional_group_from_prefix: Dict[str, argparse._ArgumentGroup] = {
            "": parser._action_groups[1],
        }
        required_group_from_prefix: Dict[str, argparse._ArgumentGroup] = {
            "": parser.add_argument_group(format_group_name("", required=True)),
        }

        # Break some API boundaries to rename the optional group.
        parser._action_groups[1].title = format_group_name("", required=False)
        positional_group = parser.add_argument_group(
            termcolor.colored("positional arguments", attrs=["bold"])
        )
        parser._action_groups = parser._action_groups[::-1]

        # Add each argument.
        for arg in self.args:
            if arg.field.positional:
                arg.add_argument(positional_group)
                continue

            if arg.lowered.required:
                target_groups, other_groups = (
                    required_group_from_prefix,
                    optional_group_from_prefix,
                )
            else:
                target_groups, other_groups = (
                    optional_group_from_prefix,
                    required_group_from_prefix,
                )

            if arg.prefix not in target_groups:
                nested_field_name = arg.prefix[:-1]
                target_groups[arg.prefix] = parser.add_argument_group(
                    format_group_name(nested_field_name, required=arg.lowered.required),
                    # Add a description, but only to the first group for a field.
                    description=self.helptext_from_nested_class_field_name.get(
                        nested_field_name
                    )
                    if arg.prefix not in other_groups
                    else None,
                )
            arg.add_argument(target_groups[arg.prefix])

        # Create subparser tree.
        if len(self.subparsers_from_name) > 0:
            prev_subparser_tree_nodes = [parser]  # Root node.
            for subparsers in self.subparsers_from_name.values():
                title = "subcommands"
                metavar = "{" + ",".join(subparsers.parser_from_name.keys()) + "}"
                if not subparsers.required:
                    title = "optional " + title
                    metavar = f"[{metavar}]"

                subparser_tree_nodes = []
                for p in prev_subparser_tree_nodes:
                    # Add subparsers to every node in previous level of the tree.
                    argparse_subparsers = p.add_subparsers(
                        dest=self.prefix
                        + _strings.SUBPARSER_DEST_FMT.format(name=subparsers.name),
                        description=subparsers.description,
                        required=subparsers.required,
                        title=title,
                        metavar=metavar,
                    )
                    for name, subparser_def in subparsers.parser_from_name.items():
                        subparser = argparse_subparsers.add_parser(name)
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

                prev_subparser_tree_nodes = subparser_tree_nodes


@dataclasses.dataclass(frozen=True)
class SubparsersSpecification:
    """Structure for defining subparsers. Each subparser is a parser with a name."""

    name: str
    description: Optional[str]
    parser_from_name: Dict[str, ParserSpecification]
    required: bool
    default_instance: Optional[Any]
    can_be_none: bool  # If underlying type is Optional[Something].

    @staticmethod
    def from_field(
        field: _fields.Field,
        type_from_typevar: Dict[TypeVar, Type],
        parent_classes: Set[Type],
        prefix: str,
        avoid_subparsers: bool,
    ) -> Optional[SubparsersSpecification]:
        # Union of classes should create subparsers.
        if get_origin(field.typ) is not Union:
            return None

        # We don't use sets here to retain order of subcommands.
        options = [type_from_typevar.get(typ, typ) for typ in get_args(field.typ)]
        options_no_none = [o for o in options if o != type(None)]  # noqa
        if not all(map(_is_possibly_nested_type, options_no_none)):
            return None

        parser_from_name: Dict[str, ParserSpecification] = {}
        for option in options_no_none:
            subparser_name = _strings.subparser_name_from_type(option)
            parser_from_name[subparser_name] = ParserSpecification.from_callable(
                option,
                description=None,
                parent_classes=parent_classes,
                parent_type_from_typevar=type_from_typevar,
                default_instance=field.default
                if isinstance(field.default, _resolver.unwrap_origin(option))
                else None,
                prefix=prefix,
                avoid_subparsers=avoid_subparsers,
            )

        # Optional if: type hint is Optional[], or a default instance is provided.
        required = True
        can_be_none = options != options_no_none  # Optional[] type.
        if can_be_none:
            required = False
        elif field.default is not None:
            required = False

        # If there are any required arguments in the default subparser, we should mark
        # the subparser group as a whole as required.
        if field.default is not None:
            default_parser = parser_from_name[
                _strings.subparser_name_from_type(type(field.default))
            ]
            if any(map(lambda arg: arg.lowered.required, default_parser.args)):
                required = True
            if any(
                map(
                    lambda subparsers: subparsers.required,
                    default_parser.subparsers_from_name.values(),
                )
            ):
                required = True

        description_parts = []
        if field.helptext is not None:
            description_parts.append(field.helptext)
        if not required and field.default is not None:
            default = _strings.subparser_name_from_type(type(field.default))
            description_parts.append(f" (default: {default})")

        return SubparsersSpecification(
            name=field.name,
            # If we wanted, we could add information about the default instance
            # automatically, as is done for normal fields. But for now we just rely on
            # the user to include it in the docstring.
            description=" ".join(description_parts),
            parser_from_name=parser_from_name,
            required=required,
            default_instance=field.default,
            can_be_none=can_be_none,
        )
