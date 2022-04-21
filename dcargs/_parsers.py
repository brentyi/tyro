"""Abstractions for creating argparse parsers from a dataclass definition."""

import argparse
import dataclasses
import warnings
from typing import Any, Dict, Generic, List, Optional, Set, Tuple, Type, TypeVar, Union

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
        # Populate default from explicit `default_instance` in `dcargs.parse()`.
        field_default_instance = getattr(parent_default_instance, field.name)
    return field_default_instance


@dataclasses.dataclass(frozen=True)
class ParserSpecification:
    """Each parser contains a list of arguments and optionally some subparsers."""

    cls: Type
    args: List[_arguments.ArgumentDefinition]
    nested_dataclass_field_names: List[str]
    subparsers: Optional["SubparsersSpecification"]

    def apply(self, parser: argparse.ArgumentParser) -> None:
        """Create defined arguments and subparsers."""

        # Put required group at start of group list.
        required_group = parser.add_argument_group("required arguments")
        parser._action_groups = parser._action_groups[::-1]

        # Add each argument.
        for arg in self.args:
            if arg.required:
                arg.add_argument(required_group)
            else:
                arg.add_argument(parser)

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
                    description=_docstrings.get_dataclass_docstring(subparser_def.cls),
                )
                subparser_def.apply(subparser)

    @staticmethod
    def from_dataclass(
        cls: Type[T],
        parent_dataclasses: Optional[Set[Type]],
        parent_type_from_typevar: Optional[Dict[TypeVar, Type]],
        default_instance: Optional[T],
    ) -> "ParserSpecification":
        """Create a parser definition from a dataclass."""

        if parent_dataclasses is None:
            parent_dataclasses = set()

        assert _resolver.is_dataclass(cls)

        cls, type_from_typevar = _resolver.resolve_generic_classes(cls)

        if parent_type_from_typevar is not None:
            for typevar, typ in type_from_typevar.items():
                if typ in parent_type_from_typevar:
                    type_from_typevar[typevar] = parent_type_from_typevar[typ]  # type: ignore

        if cls in parent_dataclasses:
            raise _instantiators.UnsupportedTypeAnnotationError(
                f"Found a cyclic dataclass dependency with type {cls}."
            )
        parent_dataclasses = parent_dataclasses | {cls}

        args = []
        nested_dataclass_field_names = []
        subparsers = None
        for field in _resolver.resolved_fields(cls):  # type: ignore

            # Ignore fields not in constructor
            if not field.init:
                continue

            field_default_instance = _get_field_default(field, default_instance)
            nested_handler = _NestedDataclassHandler(
                cls,
                field,
                type_from_typevar,
                parent_dataclasses,
                field_default_instance,
            )

            # Try to create subparsers from this field.
            subparsers_out = nested_handler.handle_unions_over_dataclasses()
            if subparsers_out is not None:
                if subparsers is not None:
                    raise _instantiators.UnsupportedTypeAnnotationError(
                        "Only one subparser (union over dataclasses) is allowed per class."
                    )

                subparsers = subparsers_out
                continue

            # Try to interpret field as a nested dataclass.
            nested_out = nested_handler.handle_nested_dataclasses()
            if nested_out is not None:
                child_args, child_nested_field_names = nested_out
                args.extend(child_args)
                nested_dataclass_field_names.extend(child_nested_field_names)
                nested_dataclass_field_names.append(field.name)
                continue

            # Handle simple fields!
            try:
                arg = _arguments.ArgumentDefinition.make_from_field(
                    cls,
                    field,
                    type_from_typevar,
                    default=field_default_instance,
                )
            except _instantiators.UnsupportedTypeAnnotationError as e:
                # Catch unsupported annotation errors, and make the error message more
                # informative.
                raise _instantiators.UnsupportedTypeAnnotationError(
                    f"Error when parsing {cls.__name__}.{field.name} of type"
                    f" {field.type}: {e.args[0]}"
                )
            args.append(arg)

        return ParserSpecification(
            cls=cls,
            args=args,
            nested_dataclass_field_names=nested_dataclass_field_names,
            subparsers=subparsers,
        )


@dataclasses.dataclass(frozen=True)
class SubparsersSpecification:
    """Structure for defining subparsers. Each subparser is a parser with a name."""

    name: str
    description: Optional[str]
    parser_from_name: Dict[str, ParserSpecification]
    required: bool
    default_instance: Optional[Any]


@dataclasses.dataclass(frozen=True)
class _NestedDataclassHandler(Generic[T]):
    """Helper for handling nested dataclasses, which are converted to either subparsers
    or prefixed fields."""

    cls: Type[T]
    field: dataclasses.Field
    type_from_typevar: Dict[TypeVar, Type]
    parent_dataclasses: Set[Type]
    default_instance: Optional[T]

    def handle_unions_over_dataclasses(
        self,
    ) -> Optional["SubparsersSpecification"]:
        """Handle unions over dataclasses, which are converted to subparsers.. Returns
        `None` if not applicable."""

        # Union of dataclasses should create subparsers.
        if get_origin(self.field.type) is not Union:
            return None

        # We don't use sets here to retain order of subcommands.
        options = [
            self.type_from_typevar.get(typ, typ) for typ in get_args(self.field.type)
        ]
        options_no_none = [o for o in options if o != type(None)]  # noqa
        if len(options_no_none) < 2 or not all(
            map(_resolver.is_dataclass, options_no_none)
        ):
            return None

        parser_from_name: Dict[str, ParserSpecification] = {}
        for option in options_no_none:
            subparser_name = _strings.subparser_name_from_type(option)

            parser_from_name[subparser_name] = ParserSpecification.from_dataclass(
                option,
                self.parent_dataclasses,
                parent_type_from_typevar=self.type_from_typevar,
                default_instance=None,
            )

        return SubparsersSpecification(
            name=self.field.name,
            # If we wanted, we could add information about the default instance
            # automatically, as is done for normal fields. But for now we just rely on
            # the user to include it in the docstring.
            description=_docstrings.get_field_docstring(self.cls, self.field.name),
            parser_from_name=parser_from_name,
            # Required if: type hint is not Optional[], or a default instance is
            # provided.
            required=(options == options_no_none) and self.default_instance is None,
            default_instance=self.default_instance,
        )

    def handle_nested_dataclasses(
        self,
    ) -> Optional[Tuple[List[_arguments.ArgumentDefinition], List[str]]]:
        """Handle nested dataclasses. Returns `None` if not applicable."""
        # Resolve field type
        field_type = (
            self.type_from_typevar[self.field.type]  # type: ignore
            if self.field.type in self.type_from_typevar  # type: ignore
            else self.field.type
        )
        if not _resolver.is_dataclass(field_type):
            return None

        # Add arguments for nested dataclasses.
        child_definition = ParserSpecification.from_dataclass(
            field_type,
            self.parent_dataclasses,
            parent_type_from_typevar=self.type_from_typevar,
            default_instance=self.default_instance,
        )

        child_args = child_definition.args
        for i, arg in enumerate(child_args):
            child_args[i] = dataclasses.replace(
                arg,
                prefix=self.field.name
                + _strings.NESTED_DATACLASS_DELIMETER
                + arg.prefix,
            )

        nested_dataclass_field_names = [
            self.field.name + _strings.NESTED_DATACLASS_DELIMETER + x
            for x in child_definition.nested_dataclass_field_names
        ]

        return child_args, nested_dataclass_field_names
