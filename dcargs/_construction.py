"""Core functionality for instantiating dataclasses from argparse namespaces."""

from typing import TYPE_CHECKING, Any, Dict, Set, Tuple, Type, TypeVar

from typing_extensions import get_args

from . import _resolver, _strings

if TYPE_CHECKING:
    from . import _parsers

T = TypeVar("T")


class FieldActionValueError(Exception):
    """Exception raised when field actions fail; this typically means that values from
    the CLI are invalid."""


DataclassType = TypeVar("DataclassType")


def construct_dataclass(
    cls: Type[DataclassType],
    parser_definition: "_parsers.ParserSpecification",
    value_from_arg: Dict[str, Any],
    field_name_prefix: str = "",
) -> Tuple[DataclassType, Set[str]]:
    """Construct a dataclass object from a dictionary of values from argparse.

    Returns dataclass object and set of used arguments."""

    assert _resolver.is_dataclass(cls)

    cls, type_from_typevar = _resolver.resolve_generic_classes(cls)

    kwargs: Dict[str, Any] = {}
    consumed_keywords: Set[str] = set()

    def get_value_from_arg(arg: str) -> Any:
        """Helper for getting values from `value_from_arg` + doing some extra
        asserts."""
        assert arg in value_from_arg
        assert arg not in consumed_keywords
        consumed_keywords.add(arg)
        return value_from_arg[arg]

    arg_from_prefixed_field_name = {}
    for arg in parser_definition.args:
        arg_from_prefixed_field_name[arg.prefix + arg.field.name] = arg

    for field in _resolver.resolved_fields(cls):  # type: ignore
        if not field.init:
            continue

        value: Any
        prefixed_field_name = field_name_prefix + field.name

        # Resolve field type.
        field_type = (
            type_from_typevar[field.type]  # type: ignore
            if field.type in type_from_typevar
            else field.type
        )

        if prefixed_field_name in arg_from_prefixed_field_name:
            # Standard arguments.
            arg = arg_from_prefixed_field_name[prefixed_field_name]
            value = get_value_from_arg(prefixed_field_name)
            if value is not None:
                try:
                    assert arg.instantiator is not None
                    value = arg.instantiator(value)
                except ValueError as e:
                    raise FieldActionValueError(
                        f"Parsing error for {arg.get_flag()}: {e.args[0]}"
                    )
        elif prefixed_field_name in parser_definition.nested_dataclass_field_names:
            # Nested dataclasses.
            value, consumed_keywords_child = construct_dataclass(
                field_type,
                parser_definition,
                value_from_arg,
                field_name_prefix=prefixed_field_name
                + _strings.NESTED_DATACLASS_DELIMETER,
            )
            consumed_keywords |= consumed_keywords_child
        else:
            # Unions over dataclasses (subparsers). This is the only other option.
            assert parser_definition.subparsers is not None
            assert field.name == parser_definition.subparsers.name

            subparser_dest = _strings.SUBPARSER_DEST_FMT.format(
                name=prefixed_field_name
            )
            subparser_name = get_value_from_arg(subparser_dest)
            if subparser_name is None:
                # No subparser selected -- this should only happen when we do either
                # Optional[Union[A, B, ...]] or Union[A, B, None], or have a
                # default/default_factory set.
                assert (
                    type(None) in get_args(field_type)
                    or parser_definition.subparsers.default_instance is not None
                )
                value = parser_definition.subparsers.default_instance
            else:
                options = map(
                    lambda x: x if x not in type_from_typevar else type_from_typevar[x],
                    get_args(field_type),
                )
                chosen_cls = None
                for option in options:
                    if _strings.subparser_name_from_type(option) == subparser_name:
                        chosen_cls = option
                        break
                assert chosen_cls is not None
                value, consumed_keywords_child = construct_dataclass(
                    chosen_cls,
                    parser_definition.subparsers.parser_from_name[subparser_name],
                    value_from_arg,
                )
                consumed_keywords |= consumed_keywords_child

        kwargs[field.name] = value

    return cls(**kwargs), consumed_keywords  # type: ignore
