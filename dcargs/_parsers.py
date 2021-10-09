import argparse
import dataclasses
from typing import Any, Dict, List, Optional, Set, Type, Union, get_type_hints

from . import _strings
from ._arguments import ArgumentDefinition, FieldRole


@dataclasses.dataclass
class Parser:
    """Simple wrapper for an `argparse.ArgumentParser` object, which also retains an
    argument group for required arguments."""

    root: argparse.ArgumentParser
    required: argparse._ArgumentGroup

    @staticmethod
    def make(parser: argparse.ArgumentParser) -> "Parser":
        return Parser(
            root=parser,  # the default argument group is "optional arguments"
            required=parser.add_argument_group("required arguments"),
        )


@dataclasses.dataclass
class ParserDefinition:
    """Each parser contains a list of arguments and optionally a subparser."""

    description: str
    args: List["ArgumentDefinition"]
    subparsers: Optional["SubparsersDefinition"]
    role_from_field: Dict[dataclasses.Field, FieldRole] = dataclasses.field(
        default_factory=dict
    )

    def apply(self, parsers: Parser) -> None:
        """Create defined arguments and subparsers."""

        # Add each argument
        for arg in self.args:
            arg.apply(parsers)

        # Add subparsers
        if self.subparsers is not None:
            subparsers = parsers.root.add_subparsers(
                dest=_strings.SUBPARSER_DEST_FMT.format(name=self.subparsers.name),
                required=self.subparsers.required,
            )
            for name, subparser_def in self.subparsers.parsers.items():
                subparser = subparsers.add_parser(
                    name,
                    description=subparser_def.description,
                )
                subparser_def.apply(Parser.make(subparser))

    @staticmethod
    def from_dataclass(
        cls: Type[Any],
        parent_dataclasses: Optional[Set[Type]] = None,
        role_from_field: Optional[Dict[dataclasses.Field, FieldRole]] = None,
    ) -> "ParserDefinition":
        """Create a parser definition from a dataclass."""

        if parent_dataclasses is None:
            parent_dataclasses = set()
        if role_from_field is None:
            role_from_field = {}

        assert dataclasses.is_dataclass(cls)
        assert (
            cls not in parent_dataclasses
        ), f"Found a cyclic dataclass dependency with type {cls}"

        args = []
        subparsers = None
        annotations = get_type_hints(cls)
        for field in dataclasses.fields(cls):
            if not field.init:
                continue

            # Resolve forward references
            field.type = annotations[field.name]

            vanilla_field: bool = True

            # Add arguments for nested dataclasses
            if dataclasses.is_dataclass(field.type):
                child_definition = ParserDefinition.from_dataclass(
                    field.type,
                    parent_dataclasses | {cls},
                    role_from_field=role_from_field,
                )
                child_args = child_definition.args
                for i, arg in enumerate(child_args):
                    child_args[i] = dataclasses.replace(
                        arg,
                        name=field.name
                        + _strings.NESTED_DATACLASS_DELIMETER
                        + arg.name,
                    )
                args.extend(child_args)

                if child_definition.subparsers is not None:
                    assert subparsers is None
                    subparsers = child_definition.subparsers

                role_from_field[field] = FieldRole.NESTED_DATACLASS
                vanilla_field = False

            # Unions of dataclasses should create subparsers
            if hasattr(field.type, "__origin__") and field.type.__origin__ is Union:
                # We don't use sets here to retain order of subcommands
                options = field.type.__args__
                options_no_none = [o for o in options if o != type(None)]  # noqa
                if all(map(dataclasses.is_dataclass, options_no_none)):
                    assert (
                        subparsers is None
                    ), "Only one Union (subparser group) is supported per dataclass"

                    subparsers = SubparsersDefinition(
                        name=field.name,
                        parsers={
                            option.__name__: ParserDefinition.from_dataclass(
                                option,
                                parent_dataclasses | {cls},
                                role_from_field,
                            )
                            for option in options_no_none
                        },
                        required=(
                            options == options_no_none
                        ),  # not required if no options
                    )
                    vanilla_field = False
                    role_from_field[field] = FieldRole.SUBPARSERS

            # Make a vanilla field
            if vanilla_field:
                args.append(ArgumentDefinition.make_from_field(cls, field))
                role_from_field[field] = args[-1].role

        return ParserDefinition(
            description=str(cls.__doc__),
            args=args,
            subparsers=subparsers,
            role_from_field=role_from_field,
        )


@dataclasses.dataclass
class SubparsersDefinition:
    """Structure for containing subparsers. Each subparser is a parser with a name."""

    name: str
    parsers: Dict[str, ParserDefinition]
    required: bool
