import argparse
import dataclasses
from typing import Any, Dict, List, Optional, Set, Tuple, Type, TypeVar, Union

from typing_extensions import get_args, get_origin

from . import _arguments, _docstrings, _resolver, _strings

T = TypeVar("T")


@dataclasses.dataclass
class ParserSpecification:
    """Each parser contains a list of arguments and optionally some subparsers."""

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
            argparse_subparsers = parser.add_subparsers(
                dest=_strings.SUBPARSER_DEST_FMT.format(name=self.subparsers.name),
                description=self.subparsers.description,
                required=self.subparsers.required,
            )
            for name, subparser_def in self.subparsers.parser_from_name.items():
                subparser = argparse_subparsers.add_parser(name)
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

        assert (
            cls not in parent_dataclasses
        ), f"Found a cyclic dataclass dependency with type {cls}"
        parent_dataclasses = parent_dataclasses | {cls}

        args = []
        nested_dataclass_field_names = []
        subparsers = None
        for field in _resolver.resolved_fields(cls):  # type: ignore

            # Ignore fields not in constructor
            if not field.init:
                continue

            field_parser = _NestedDataclassHandler(
                cls,
                field,
                type_from_typevar,
                parent_dataclasses,
                default_instance,
            )

            # Try to create subparsers from this field.
            subparsers_out = field_parser.handle_unions_over_dataclasses()
            if subparsers_out is not None:
                assert (
                    subparsers is None
                ), "Only one subparser (union over dataclasses) is allowed per class"

                subparsers = subparsers_out
                continue

            # Try to interpret field as a nested dataclass.
            nested_out = field_parser.handle_nested_dataclasses()
            if nested_out is not None:

                child_args, child_nested_field_names = nested_out
                args.extend(child_args)
                nested_dataclass_field_names.extend(child_nested_field_names)
                nested_dataclass_field_names.append(field.name)
                continue

            # Handle simple fields!
            arg = _arguments.ArgumentDefinition.make_from_field(
                cls,
                field,
                type_from_typevar,
                default_override=getattr(default_instance, field.name)
                if default_instance is not None
                else None,
            )
            args.append(arg)

        return ParserSpecification(
            args=args,
            nested_dataclass_field_names=nested_dataclass_field_names,
            subparsers=subparsers,
        )


@dataclasses.dataclass
class SubparsersSpecification:
    """Structure for defining subparsers. Each subparser is a parser with a name."""

    name: str
    description: Optional[str]
    parser_from_name: Dict[str, ParserSpecification]
    required: bool


@dataclasses.dataclass
class _NestedDataclassHandler:
    """Helper functions for handling nested dataclasses, which are converted to either
    subparsers or prefixed fields."""

    cls: Type
    field: dataclasses.Field
    type_from_typevar: Dict[TypeVar, Type]
    parent_dataclasses: Set[Type]
    default_instance: Any

    def handle_unions_over_dataclasses(
        self,
    ) -> Optional["SubparsersSpecification"]:
        """Handle unions over dataclasses, which are converted to subparsers.. Returns
        `None` if not applicable."""

        # Union of dataclasses should create subparsers.
        if get_origin(self.field.type) is not Union:
            return None

        # We don't use sets here to retain order of subcommands.
        options = map(
            lambda x: x
            if x not in self.type_from_typevar
            else self.type_from_typevar[x],
            get_args(self.field.type),
        )
        options_no_none = [o for o in options if o != type(None)]  # noqa
        if len(options_no_none) < 2 or not all(
            map(_resolver.is_dataclass, options_no_none)
        ):
            return None

        assert (
            self.field.default == dataclasses.MISSING
        ), "Default dataclass value not yet supported for subparser definitions"

        parser_from_name: Dict[str, ParserSpecification] = {}
        for option in options_no_none:
            subparser_name = _strings.subparser_name_from_type(option)

            parser_from_name[subparser_name] = ParserSpecification.from_dataclass(
                option,
                self.parent_dataclasses,
                parent_type_from_typevar=self.type_from_typevar,
                default_instance=None,
            )

        subparsers = SubparsersSpecification(
            name=self.field.name,
            description=_docstrings.get_field_docstring(self.cls, self.field.name),
            parser_from_name=parser_from_name,
            required=(options == options_no_none),  # Not required if no options.
        )

        return subparsers

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
        default = None
        if self.default_instance is not None:
            default = getattr(self.default_instance, self.field.name)
        elif self.field.default is not dataclasses.MISSING:
            default = self.field.default

        child_definition = ParserSpecification.from_dataclass(
            field_type,
            self.parent_dataclasses,
            parent_type_from_typevar=self.type_from_typevar,
            default_instance=default,
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
