"""Core functionality for calling functions with arguments specified by argparse
namespaces."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Set, Tuple, TypeVar

from typing_extensions import get_args

from . import _fields, _parsers, _resolver, _strings


class FieldActionValueError(Exception):
    """Exception raised when field actions fail; this typically means that values from
    the CLI are invalid."""


T = TypeVar("T")


def call_from_args(
    f: Callable[..., T],
    parser_definition: _parsers.ParserSpecification,
    value_from_arg: Dict[str, Any],
    field_name_prefix: str = "",
) -> Tuple[T, Set[str]]:
    """Call `f` with arguments specified by a dictionary of values from argparse.

    Returns the output of `f` and a set of used arguments."""

    f, type_from_typevar = _resolver.resolve_generic_types(f)

    args: List[str] = []
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

    for field in _fields.field_list_from_callable(f, default_instance=None):  # type: ignore
        value: Any
        prefixed_field_name = field_name_prefix + field.name

        # Resolve field type.
        field_type = (
            type_from_typevar[field.typ]  # type: ignore
            if field.typ in type_from_typevar
            else field.typ
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
        elif (
            prefixed_field_name
            in parser_definition.helptext_from_nested_class_field_name
        ):
            # Nested callable.
            value, consumed_keywords_child = call_from_args(
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
                chosen_f = None
                for option in options:
                    if _strings.subparser_name_from_type(option) == subparser_name:
                        chosen_f = option
                        break
                assert chosen_f is not None
                value, consumed_keywords_child = call_from_args(
                    chosen_f,
                    parser_definition.subparsers.parser_from_name[subparser_name],
                    value_from_arg,
                )
                consumed_keywords |= consumed_keywords_child

        if field.positional:
            args.append(value)
        else:
            kwargs[field.name] = value

    return f(*args, **kwargs), consumed_keywords  # type: ignore
