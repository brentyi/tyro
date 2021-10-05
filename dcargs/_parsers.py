import argparse
import dataclasses
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type, Union, get_type_hints

from . import _strings
from ._arguments import ArgumentDefinition


@dataclasses.dataclass
class Parser:
    """Simple wrapper for an `argparse.ArgumentParser` object, which also retrains an
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

    def apply(self, parsers: Parser) -> None:
        """Create defined arguments and subparsers."""

        # Add each argument
        for arg in self.args:
            arg.apply(parsers)

        # Add subparsers
        if self.subparsers is not None:
            subparsers = parsers.root.add_subparsers(
                dest=_strings.SUBPARSER_DEST_FMT.format(name=self.subparsers.name),
                required=True,  # TODO: make a constant
            )
            for name, subparser_def in self.subparsers.parsers.items():
                subparser = subparsers.add_parser(
                    name,
                    description=subparser_def.description,
                )
                subparser_def.apply(Parser.make(subparser))

    @staticmethod
    def from_dataclass(cls: Type[Any]) -> "ParserDefinition":
        """Create a parser definition from a dataclass."""

        assert dataclasses.is_dataclass(cls)

        args = []
        subparsers = None
        for field in dataclasses.fields(cls):
            if not field.init:
                continue

            vanilla_field: bool = True

            # Add arguments for nested dataclasses
            if dataclasses.is_dataclass(field.type):
                child_definition = ParserDefinition.from_dataclass(field.type)
                child_args = child_definition.args
                for arg in child_args:
                    arg.name = (
                        field.name + _strings.NESTED_DATACLASS_DELIMETER + arg.name
                    )
                args.extend(child_args)

                if child_definition.subparsers is not None:
                    assert subparsers is None
                    subparsers = child_definition.subparsers

                vanilla_field = False

            # Unions of dataclasses should create subparsers
            if hasattr(field.type, "__origin__") and field.type.__origin__ is Union:
                options = get_type_hints(cls)[field.name].__args__
                if all(map(dataclasses.is_dataclass, options)):
                    assert (
                        subparsers is None
                    ), "Only one Union (subparser group) is supported per dataclass"

                    subparsers = SubparsersDefinition(
                        name=field.name,
                        parsers={
                            option.__name__: ParserDefinition.from_dataclass(option)
                            for option in options
                        },
                    )
                    vanilla_field = False

            # Make a vanilla field
            if vanilla_field:
                args.append(ArgumentDefinition.make_from_field(cls, field))

        return ParserDefinition(
            description=str(cls.__doc__),
            args=args,
            subparsers=subparsers,
        )


@dataclasses.dataclass
class SubparsersDefinition:
    """Structure for containing subparsers. Each subparser is a parser with a name."""

    name: str
    parsers: Dict[str, ParserDefinition]
