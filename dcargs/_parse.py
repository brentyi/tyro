import argparse
import dataclasses
import enum
from typing import Any, Dict, Optional, Sequence, Type, TypeVar, Union

from . import _strings
from ._parsers import Parser, ParserDefinition

DataclassType = TypeVar("DataclassType")


def parse(
    cls: Type[DataclassType],
    description: str = "",
    args: Optional[Sequence[str]] = None,
) -> DataclassType:
    """Populate a dataclass via CLI args."""
    assert dataclasses.is_dataclass(cls)

    parser_definition = ParserDefinition.from_dataclass(cls, parent_dataclasses=set())

    root_parser = argparse.ArgumentParser(
        description=_strings.dedent(description),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser_definition.apply(Parser.make(root_parser))
    namespace = root_parser.parse_args(args)

    return _construct_dataclass(cls, vars(namespace))


def _construct_dataclass(
    cls: Type[DataclassType], values: Dict[str, Any]
) -> DataclassType:
    """Construct a dataclass object from a dictionary of values from argparse."""

    assert dataclasses.is_dataclass(cls)
    fields = dataclasses.fields(cls)

    kwargs: Dict[str, Any] = {}

    for field in fields:
        if not field.init:
            continue

        value: Any

        # Handle enums
        if isinstance(field.type, type) and issubclass(field.type, enum.Enum):
            value = field.type[values[field.name]]

        # Nested dataclasses
        elif dataclasses.is_dataclass(field.type):
            arg_prefix = field.name + _strings.NESTED_DATACLASS_DELIMETER
            value = _construct_dataclass(
                field.type,
                values={
                    k[len(arg_prefix) :]: v
                    for k, v in values.items()
                    if k.startswith(arg_prefix)
                },
            )

        # Unions over dataclasses (subparsers)
        elif (
            hasattr(field.type, "__origin__")
            and field.type.__origin__ is Union
            and all(map(dataclasses.is_dataclass, field.type.__args__))
        ):
            subparser_dest = _strings.SUBPARSER_DEST_FMT.format(name=field.name)
            assert subparser_dest in values.keys()
            options = field.type.__args__
            chosen_cls = None
            for option in options:
                if option.__name__ == values[subparser_dest]:
                    chosen_cls = option
                    break
            assert chosen_cls is not None
            value = _construct_dataclass(chosen_cls, values)

        # General case
        else:
            value = values[field.name]

        kwargs[field.name] = value

    return cls(**kwargs)  # type: ignore
