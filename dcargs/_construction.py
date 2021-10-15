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


@dataclasses.dataclass
class ConstructionMetadata:
    """Metadata recorded during parsing that's needed for reconstructing dataclasses."""

    role_from_field: Dict[dataclasses.Field, FieldRole] = dataclasses.field(
        default_factory=dict
    )
    subparser_name_from_type: Dict[Type, str] = dataclasses.field(default_factory=dict)

    def update(self, other: "ConstructionMetadata") -> None:
        self.role_from_field.update(other.role_from_field)
        self.subparser_name_from_type.update(other.subparser_name_from_type)


def construct_dataclass(
    cls: Type[DataclassType],
    value_from_arg: Dict[str, Any],
    metadata: ConstructionMetadata,
    field_name_prefix: str = "",
) -> DataclassType:
    """Construct a dataclass object from a dictionary of values from argparse.
    Mutates `value_from_arg`."""

    assert _resolver.is_dataclass(cls)

    cls, _type_from_typevar = _resolver.resolve_generic_dataclasses(cls)

    kwargs: Dict[str, Any] = {}

    for field in _resolver.resolved_fields(cls):  # type: ignore
        if not field.init:
            continue

        value: Any
        role = metadata.role_from_field[field]

        prefixed_field_name = field_name_prefix + field.name

        if role is FieldRole.ENUM:
            # Handle enums
            value = field.type[value_from_arg.pop(prefixed_field_name)]
        elif role is FieldRole.NESTED_DATACLASS:
            # Nested dataclasses
            value = construct_dataclass(
                field.type,
                value_from_arg,
                metadata,
                field_name_prefix=prefixed_field_name
                + _strings.NESTED_DATACLASS_DELIMETER,
            )  # TODO: need to strip prefixes here. not sure how
        elif role is FieldRole.SUBPARSERS:
            # Unions over dataclasses (subparsers)
            subparser_dest = _strings.SUBPARSER_DEST_FMT.format(
                name=prefixed_field_name
            )
            subparser_name = value_from_arg.pop(subparser_dest)
            if subparser_name is None:
                # No subparser selected -- this should only happen when we do either
                # Optional[Union[A, B, ...]] or Union[A, B, None] -- note that these are
                # equivalent
                assert type(None) in field.type.__args__
                value = None
            else:
                options = field.type.__args__
                chosen_cls = None
                for option in options:
                    if metadata.subparser_name_from_type[option] == subparser_name:
                        chosen_cls = option
                        break
                assert chosen_cls is not None
                value = construct_dataclass(
                    chosen_cls,
                    value_from_arg,
                    metadata,
                )
        elif role is FieldRole.TUPLE:
            # For sequences, argparse always gives us lists -- sometimes we want tuples
            value = value_from_arg.pop(prefixed_field_name)
            if value is not None:
                value = tuple(value)

        elif role is FieldRole.VANILLA_FIELD:
            # General case
            value = value_from_arg.pop(prefixed_field_name)
        else:
            assert False

        kwargs[field.name] = value

    return cls(**kwargs)  # type: ignore
