import dataclasses
import enum
from typing import Any, Dict, Type, TypeVar, Union

from typing_extensions import _GenericAlias  # type: ignore

from . import _resolver, _strings

DataclassType = TypeVar("DataclassType", bound=Union[Type, _GenericAlias])


class FieldRole(enum.Enum):
    """Enum for specifying special behaviors for ."""

    VANILLA_FIELD = enum.auto()
    TUPLE = enum.auto()
    ENUM = enum.auto()
    NESTED_DATACLASS = enum.auto()  # Singular nested dataclass
    SUBPARSERS = enum.auto()  # Unions over dataclasses


def construct_dataclass(
    cls: Type[DataclassType],
    role_from_field: Dict[dataclasses.Field, FieldRole],
    values: Dict[str, Any],
) -> DataclassType:
    """Construct a dataclass object from a dictionary of values from argparse."""

    assert _resolver.is_dataclass(cls)

    cls, _type_from_typevar = _resolver.resolve_generic_dataclasses(cls)

    kwargs: Dict[str, Any] = {}

    for field in _resolver.resolved_fields(cls):  # type: ignore
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
            value = construct_dataclass(
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
                value = construct_dataclass(chosen_cls, role_from_field, values)
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
