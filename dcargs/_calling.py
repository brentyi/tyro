"""Core functionality for calling functions with arguments specified by argparse
namespaces."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Set, Tuple, TypeVar, Union

from typing_extensions import get_args, get_origin

from . import _arguments, _fields, _parsers, _resolver, _strings


class InstantiationError(Exception):
    """Exception raised when instantiation fail; this typically means that values from
    the CLI are invalid."""


T = TypeVar("T")


def call_from_args(
    f: Callable[..., T],
    parser_definition: _parsers.ParserSpecification,
    default_instance: Union[T, _fields.NonpropagatingMissingType],
    value_from_prefixed_field_name: Dict[str, Any],
    field_name_prefix: str,
    avoid_subparsers: bool,
) -> Tuple[T, Set[str]]:
    """Call `f` with arguments specified by a dictionary of values from argparse.

    Returns the output of `f` and a set of used arguments."""

    f, type_from_typevar = _resolver.resolve_generic_types(f)

    args: List[str] = []
    kwargs: Dict[str, Any] = {}
    consumed_keywords: Set[str] = set()

    def get_value_from_arg(prefixed_field_name: str) -> Any:
        """Helper for getting values from `value_from_arg` + doing some extra
        asserts."""
        assert prefixed_field_name in value_from_prefixed_field_name
        return value_from_prefixed_field_name[prefixed_field_name]

    arg_from_prefixed_field_name: Dict[str, _arguments.ArgumentDefinition] = {}
    for arg in parser_definition.args:
        arg_from_prefixed_field_name[arg.prefix + arg.field.name] = arg

    for field in _fields.field_list_from_callable(f, default_instance=default_instance):  # type: ignore
        value: Any
        prefixed_field_name = field_name_prefix + field.name

        # Resolve field type.
        field_type = (
            type_from_typevar[field.typ]  # type: ignore
            if field.typ in type_from_typevar
            else field.typ
        )

        if prefixed_field_name in arg_from_prefixed_field_name:
            assert prefixed_field_name not in consumed_keywords

            # Standard arguments.
            arg = arg_from_prefixed_field_name[prefixed_field_name]
            consumed_keywords.add(prefixed_field_name)
            if not arg.lowered.is_fixed():
                value = get_value_from_arg(prefixed_field_name)
                if value not in _fields.MISSING_SINGLETONS:
                    try:
                        assert arg.lowered.instantiator is not None
                        value = arg.lowered.instantiator(value)
                    except ValueError as e:
                        raise InstantiationError(
                            f"Parsing error for {arg.lowered.name_or_flag}: {e.args[0]}"
                        )
                else:
                    value = arg.field.default
            else:
                assert arg.field.default not in _fields.MISSING_SINGLETONS
                value = arg.field.default
                parsed_value = value_from_prefixed_field_name.get(prefixed_field_name)
                if parsed_value not in _fields.MISSING_SINGLETONS:
                    raise InstantiationError(
                        f"{arg.lowered.name_or_flag}={parsed_value} was passed in, but"
                        " is a fixed argument that cannot be parsed"
                    )
        elif (
            prefixed_field_name
            in parser_definition.helptext_from_nested_class_field_name
        ):
            # Nested callable.
            if get_origin(field_type) is Union:
                assert avoid_subparsers
                field_type = type(field.default)
            value, consumed_keywords_child = call_from_args(
                field_type,
                parser_definition,
                field.default,
                value_from_prefixed_field_name,
                field_name_prefix=prefixed_field_name + _strings.NESTED_FIELD_DELIMETER,
                avoid_subparsers=avoid_subparsers,
            )
            consumed_keywords |= consumed_keywords_child
        else:
            # Unions over dataclasses (subparsers). This is the only other option.
            assert len(parser_definition.subparsers_from_name) > 0
            assert field.name in parser_definition.subparsers_from_name

            subparser_dest = _strings.SUBPARSER_DEST_FMT.format(
                name=prefixed_field_name
            )
            if subparser_dest in value_from_prefixed_field_name:
                subparser_name = get_value_from_arg(subparser_dest)
            else:
                default_instance = parser_definition.subparsers_from_name[
                    field.name
                ].default_instance
                assert default_instance is not None
                subparser_name = None
            if subparser_name is None:
                # No subparser selected -- this should only happen when we do either
                # Optional[Union[A, B, ...]] or Union[A, B, None], or have a
                # default/default_factory set.
                assert (
                    type(None) in get_args(field_type)
                    or parser_definition.subparsers_from_name[
                        field.name
                    ].default_instance
                    is not None
                )
                value = parser_definition.subparsers_from_name[
                    field.name
                ].default_instance
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
                    parser_definition.subparsers_from_name[field.name].parser_from_name[
                        subparser_name
                    ],
                    field.default if type(field.default) is chosen_f else None,
                    value_from_prefixed_field_name,
                    field_name_prefix=prefixed_field_name
                    + _strings.NESTED_FIELD_DELIMETER,
                    avoid_subparsers=avoid_subparsers,
                )
                consumed_keywords |= consumed_keywords_child

        if value is not _fields.EXCLUDE_FROM_CALL:
            if field.positional:
                args.append(value)
            else:
                kwargs[field.name] = value

    return _resolver.unwrap_origin(f)(*args, **kwargs), consumed_keywords  # type: ignore
