"""Abstractions for creating argparse parsers from a dataclass definition."""

from __future__ import annotations

import argparse
import collections.abc
import dataclasses
import inspect
import itertools
import warnings
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
    get_type_hints,
)

import docstring_parser
import termcolor
import typing_extensions
from typing_extensions import get_args, get_origin

from . import _arguments, _docstrings, _instantiators, _resolver, _strings

T = TypeVar("T")


def _ensure_dataclass_instance_used_as_default_is_frozen(
    field: dataclasses.Field, default_instance: Any
) -> None:
    """Ensure that a dataclass type used directly as a default value is marked as
    frozen."""
    assert dataclasses.is_dataclass(default_instance)
    cls = type(default_instance)
    if not cls.__dataclass_params__.frozen:
        warnings.warn(
            f"Mutable type {cls} is used as a default value for `{field.name}`. This is"
            " dangerous! Consider using `dataclasses.field(default_factory=...)` or"
            f" marking {cls} as frozen."
        )


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


def _is_parsable_type(typ: Any) -> bool:
    """Heuristics for determining whether a type can be treated as a single argument.
    This is true for built-in types like ints, strings, bools, etc, as well as
    pathlib.Path."""

    origin = get_origin(typ)
    if origin is not None:
        typ = origin

    # Known parsable types: builtins like int/str/float/bool, collections, annotations.
    if typ in _known_parsable_types:
        return True

    # Simple heuristic: dataclasses should be treated as nested objects and are not
    # parsable.
    if dataclasses.is_dataclass(typ):
        return False

    # Non-parsable types like nested (data)classes should have fully type-annotated
    # inputs. If any inputs are unannotated (for example, in the case of pathlib.Path),
    # we can assume the type is parsable.
    for param in inspect.signature(typ).parameters.values():
        if param.annotation is inspect.Parameter.empty:
            return True

    return False


def _get_field_default(
    field: dataclasses.Field, parent_default_instance: Any
) -> Optional[Any]:
    """Helper for getting the default instance for a field."""
    field_default_instance = None
    if field.default is not dataclasses.MISSING:
        # Populate default from usual default value, or
        # `dataclasses.field(default=...)`.
        field_default_instance = field.default
        if dataclasses.is_dataclass(field_default_instance):
            _ensure_dataclass_instance_used_as_default_is_frozen(
                field, field_default_instance
            )
    elif field.default_factory is not dataclasses.MISSING:
        # Populate default from `dataclasses.field(default_factory=...)`.
        field_default_instance = field.default_factory()

    if parent_default_instance is not None:
        # Populate default from some parent, eg `default_instance` in `dcargs.cli()`.
        field_default_instance = getattr(parent_default_instance, field.name)
    return field_default_instance


@dataclasses.dataclass(frozen=True)
class Field:
    name: str
    typ: Type
    default: Any
    helptext: Optional[str]
    positional: bool


def _fields_from_callable(f: Callable, default_instance: Any) -> List[Field]:
    """Generate a list of generic 'field' objects corresponding to an input callable.

    `f` can be from a dataclass type, regular class type, or function."""
    out = []
    f, type_from_typevar = _resolver.resolve_generic_types(f)
    if _resolver.is_dataclass(f):
        for field in _resolver.resolved_fields(f):
            if not field.init:
                continue
            out.append(
                Field(
                    name=field.name,
                    typ=field.type,
                    default=_get_field_default(field, default_instance),
                    helptext=_docstrings.get_field_docstring(cast(Type, f), field.name),
                    positional=False,
                )
            )
    else:
        if isinstance(f, type):
            hints = get_type_hints(f.__init__)  # type: ignore
            docstring = inspect.getdoc(f.__init__)  # type: ignore
        else:
            hints = get_type_hints(f)
            docstring = inspect.getdoc(f)

        docstring_from_name = {}
        if docstring is not None:
            for param_doc in docstring_parser.parse(docstring).params:
                docstring_from_name[param_doc.arg_name] = param_doc.description

        for param in inspect.signature(f).parameters.values():
            field_docstring = (
                _docstrings.get_field_docstring(cast(Type, f), param.name)
                if isinstance(f, type) and hasattr(f, "mro")
                else None
            )
            out.append(
                Field(
                    name=param.name,
                    # Note that param.annotation does not resolve forward references.
                    typ=hints[param.name],
                    default=param.default
                    if param.default is not inspect.Parameter.empty
                    else None,
                    helptext=docstring_from_name.get(
                        param.name,
                        field_docstring,
                    ),
                    positional=param.kind is inspect.Parameter.POSITIONAL_ONLY,
                )
            )
    return out


@dataclasses.dataclass(frozen=True)
class ParserSpecification:
    """Each parser contains a list of arguments and optionally some subparsers."""

    f: Callable
    args: List[_arguments.ArgumentDefinition]
    helptext_from_nested_class_field_name: Dict[str, Optional[str]]
    subparsers: Optional[SubparsersSpecification]

    @staticmethod
    def from_callable(
        f: Callable,
        parent_classes: Set[Type],
        parent_type_from_typevar: Optional[Dict[TypeVar, Type]],
        default_instance: Optional[T],
    ) -> ParserSpecification:
        """Create a parser definition from a callable."""

        # Resolve generic types.
        f, type_from_typevar = _resolver.resolve_generic_types(f)
        if parent_type_from_typevar is not None:
            for typevar, typ in type_from_typevar.items():
                if typ in parent_type_from_typevar:
                    type_from_typevar[typevar] = parent_type_from_typevar[typ]  # type: ignore

        # Cycle detection.
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
        subparsers = None
        for field in _fields_from_callable(f=f, default_instance=default_instance):

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

            get_origin(field.typ)
            # (1) Handle Unions over callables; these result in subparsers.
            subparsers_attempt = SubparsersSpecification.from_field(
                field,
                type_from_typevar=type_from_typevar,
                parent_classes=parent_classes,
            )
            if subparsers_attempt is not None:
                if subparsers is not None:
                    raise _instantiators.UnsupportedTypeAnnotationError(
                        "Only one set of subparsers is allowed."
                    )
                subparsers = subparsers_attempt
                continue

            # (2) Handle primitive types. These produce a single argument!
            if _is_parsable_type(field.typ):
                args.append(
                    _arguments.ArgumentDefinition.from_field(field, type_from_typevar)
                )
                continue

            # (3) Handle nested callables.
            nested_parser = ParserSpecification.from_callable(
                field.typ,
                parent_classes=parent_classes,
                parent_type_from_typevar=type_from_typevar,
                default_instance=field.default,
            )
            for arg in nested_parser.args:
                args.append(
                    dataclasses.replace(
                        arg,
                        prefix=field.name
                        + _strings.NESTED_DATACLASS_DELIMETER
                        + arg.prefix,
                    )
                )
            for k, v in nested_parser.helptext_from_nested_class_field_name.items():
                helptext_from_nested_class_field_name[
                    field.name + _strings.NESTED_DATACLASS_DELIMETER + k
                ] = v
            helptext_from_nested_class_field_name[field.name] = field.helptext

        return ParserSpecification(
            f=f,
            args=args,
            helptext_from_nested_class_field_name=helptext_from_nested_class_field_name,
            subparsers=subparsers,
        )

    def apply(self, parser: argparse.ArgumentParser) -> None:
        """Create defined arguments and subparsers."""

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

            if arg.required:
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
                    format_group_name(nested_field_name, required=arg.required),
                    # Add a description, but only to the first group for a field.
                    description=self.helptext_from_nested_class_field_name[
                        nested_field_name
                    ]
                    if arg.prefix not in other_groups
                    else None,
                )
            arg.add_argument(target_groups[arg.prefix])

        # Add subparsers.
        if self.subparsers is not None:
            title = "subcommands"
            metavar = "{" + ",".join(self.subparsers.parser_from_name.keys()) + "}"
            if not self.subparsers.required:
                title = "optional " + title
                metavar = f"[{metavar}]"

            argparse_subparsers = parser.add_subparsers(
                dest=_strings.SUBPARSER_DEST_FMT.format(name=self.subparsers.name),
                description=self.subparsers.description,
                required=self.subparsers.required,
                title=title,
                metavar=metavar,
            )
            for name, subparser_def in self.subparsers.parser_from_name.items():
                subparser = argparse_subparsers.add_parser(
                    name,
                    description=_docstrings.get_callable_description(subparser_def.f),
                )
                subparser_def.apply(subparser)


@dataclasses.dataclass(frozen=True)
class SubparsersSpecification:
    """Structure for defining subparsers. Each subparser is a parser with a name."""

    name: str
    description: Optional[str]
    parser_from_name: Dict[str, ParserSpecification]
    required: bool
    default_instance: Optional[Any]

    @staticmethod
    def from_field(
        field: Field,
        type_from_typevar: Dict[TypeVar, Type],
        parent_classes: Set[Type],
    ) -> Optional[SubparsersSpecification]:
        # Union of classes should create subparsers.
        if get_origin(field.typ) is not Union:
            return None

        # We don't use sets here to retain order of subcommands.
        options = [type_from_typevar.get(typ, typ) for typ in get_args(field.typ)]
        options_no_none = [o for o in options if o != type(None)]  # noqa
        if len(options_no_none) < 2 or any(map(_is_parsable_type, options_no_none)):
            return None

        parser_from_name: Dict[str, ParserSpecification] = {}
        for option in options_no_none:
            subparser_name = _strings.subparser_name_from_type(option)
            parser_from_name[subparser_name] = ParserSpecification.from_callable(
                option,
                parent_classes,
                parent_type_from_typevar=type_from_typevar,
                default_instance=None,
            )

        return SubparsersSpecification(
            name=field.name,
            # If we wanted, we could add information about the default instance
            # automatically, as is done for normal fields. But for now we just rely on
            # the user to include it in the docstring.
            description=field.helptext,
            parser_from_name=parser_from_name,
            # Required if: type hint is not Optional[], or a default instance is
            # provided.
            required=(options == options_no_none) and field.default is None,
            default_instance=field.default,
        )
