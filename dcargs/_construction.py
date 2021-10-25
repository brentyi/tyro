import dataclasses
import enum
from typing import Any, Dict, Set, Tuple, Type, TypeVar, Union

from typing_extensions import _GenericAlias  # type: ignore

from . import _resolver, _strings

DataclassType = TypeVar("DataclassType", bound=Union[Type, _GenericAlias])


class FieldRole(enum.Enum):
    """Enum for specifying special behaviors for ."""

    VANILLA_FIELD = enum.auto()
    TUPLE = enum.auto()
    ENUM = enum.auto()
    NESTED_DATACLASS = enum.auto()  # Singular nested dataclass.
    SUBPARSERS = enum.auto()  # Unions over dataclasses.


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
) -> Tuple[DataclassType, Set[str]]:
    """Construct a dataclass object from a dictionary of values from argparse.

    Returns dataclass object and set of used arguments."""

    assert _resolver.is_dataclass(cls)

    cls, type_from_typevar = _resolver.resolve_generic_dataclasses(cls)

    kwargs: Dict[str, Any] = {}
    consumed_keywords: Set[str] = set()

    def get_value_from_arg(arg: str) -> Any:
        """Helper for getting values from `value_from_arg` + doing some extra
        asserts."""
        assert arg in value_from_arg
        assert arg not in consumed_keywords
        consumed_keywords.add(arg)
        return value_from_arg[arg]

    for field in _resolver.resolved_fields(cls):  # type: ignore
        if not field.init:
            continue

        value: Any
        role = metadata.role_from_field[field]

        prefixed_field_name = field_name_prefix + field.name

        # Resolve field type
        field_type = (
            type_from_typevar[field.type]  # type: ignore
            if field.type in type_from_typevar
            else field.type
        )

        if role is FieldRole.ENUM:
            # Handle enums.
            value = field_type[get_value_from_arg(prefixed_field_name)]
        elif role is FieldRole.NESTED_DATACLASS:
            # Nested dataclasses.
            value, consumed_keywords_child = construct_dataclass(
                field_type,
                value_from_arg,
                metadata,
                field_name_prefix=prefixed_field_name
                + _strings.NESTED_DATACLASS_DELIMETER,
            )
            consumed_keywords |= consumed_keywords_child
        elif role is FieldRole.SUBPARSERS:
            # Unions over dataclasses (subparsers).
            subparser_dest = _strings.SUBPARSER_DEST_FMT.format(
                name=prefixed_field_name
            )
            subparser_name = get_value_from_arg(subparser_dest)
            if subparser_name is None:
                # No subparser selected -- this should only happen when we do either
                # Optional[Union[A, B, ...]] or Union[A, B, None].
                assert type(None) in field_type.__args__
                value = None
            else:
                options = field_type.__args__
                options = map(
                    lambda x: x if x not in type_from_typevar else type_from_typevar[x],
                    field_type.__args__,
                )
                chosen_cls = None
                for option in options:
                    if metadata.subparser_name_from_type[option] == subparser_name:
                        chosen_cls = option
                        break
                assert chosen_cls is not None
                value, consumed_keywords_child = construct_dataclass(
                    chosen_cls,
                    value_from_arg,
                    metadata,
                )
                consumed_keywords |= consumed_keywords_child
        elif role is FieldRole.TUPLE:
            # For sequences, argparse always gives us lists. Sometimes we want tuples.
            value = get_value_from_arg(prefixed_field_name)
            if value is not None:
                value = tuple(value)

        elif role is FieldRole.VANILLA_FIELD:
            # General case.
            value = get_value_from_arg(prefixed_field_name)
        else:
            assert False

        kwargs[field.name] = value

    return cls(**kwargs), consumed_keywords  # type: ignore
