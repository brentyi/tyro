import argparse
import dataclasses
from typing import Any, Dict, Optional, Sequence, Type, TypeVar

from . import _strings
from ._arguments import FieldRole
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

    return _construct_dataclass(cls, parser_definition.role_from_field, vars(namespace))


def _construct_dataclass(
    cls: Type[DataclassType],
    role_from_field: Dict[dataclasses.Field, FieldRole],
    values: Dict[str, Any],
) -> DataclassType:
    """Construct a dataclass object from a dictionary of values from argparse."""

    assert dataclasses.is_dataclass(cls)
    fields = dataclasses.fields(cls)

    kwargs: Dict[str, Any] = {}

    for field in fields:
        if not field.init:
            continue

        value: Any
        role = role_from_field[field]

        if role is FieldRole.ENUM:
            # Handle enums
            value = field.type[values[field.name]]
        elif role is FieldRole.NESTED_DATACLASS:
            # Nested dataclasses
            arg_prefix = field.name + _strings.NESTED_DATACLASS_DELIMETER
            value = _construct_dataclass(
                field.type,
                role_from_field,
                values={
                    k[len(arg_prefix) :]: v
                    for k, v in values.items()
                    if k.startswith(arg_prefix)
                },
            )
        elif role is FieldRole.SUBPARSERS:
            # Unions over dataclasses (subparsers)
            subparser_dest = _strings.SUBPARSER_DEST_FMT.format(name=field.name)
            if values[subparser_dest] is None:
                # No subparser selected -- this should only happen when we do either
                # Optional[Union[A, B, ...]] or Union[A, B, None] -- note that these are
                # equivalent
                assert type(None) in field.type.__args__
                value = None
            else:
                assert subparser_dest in values.keys()
                options = field.type.__args__
                chosen_cls = None
                for option in options:
                    if option.__name__ == values[subparser_dest]:
                        chosen_cls = option
                        break
                assert chosen_cls is not None
                value = _construct_dataclass(chosen_cls, role_from_field, values)
        elif role is FieldRole.TUPLE:
            # For sequences, argparse always gives us lists -- sometimes we want tuples
            value = (
                tuple(values[field.name]) if values[field.name] is not None else None
            )
        elif role is FieldRole.VANILLA_FIELD:
            # General case
            value = values[field.name]
        else:
            assert False

        kwargs[field.name] = value

    return cls(**kwargs)  # type: ignore
