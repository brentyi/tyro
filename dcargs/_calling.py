"""Core functionality for calling functions with arguments specified by argparse
namespaces."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Sequence, Set, Tuple, TypeVar, Union

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
    f = _resolver.narrow_type(f, default_instance)

    args: List[Any] = []
    kwargs: Dict[str, Any] = {}
    consumed_keywords: Set[str] = set()

    def get_value_from_arg(prefixed_field_name: str) -> Any:
        """Helper for getting values from `value_from_arg` + doing some extra
        asserts."""
        assert prefixed_field_name in value_from_prefixed_field_name
        return value_from_prefixed_field_name[prefixed_field_name]

    arg_from_prefixed_field_name: Dict[str, _arguments.ArgumentDefinition] = {}
    for arg in parser_definition.args:
        arg_from_prefixed_field_name[
            _strings.make_field_name([arg.prefix, arg.field.name])
        ] = arg

    for field in _fields.field_list_from_callable(
        f, default_instance=default_instance
    ):  # type: ignore
        value: Any
        prefixed_field_name = _strings.make_field_name([field_name_prefix, field.name])

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

                if value in _fields.MISSING_SINGLETONS:
                    value = arg.field.default
                else:
                    if arg.lowered.nargs == "?":
                        # Special case for optional positional arguments: this is the
                        # only time that arguments don't come back as a list.
                        value = [value]

                    try:
                        assert arg.lowered.instantiator is not None
                        value = arg.lowered.instantiator(value)
                    except ValueError as e:
                        raise InstantiationError(
                            f"Parsing error for {arg.lowered.name_or_flag}: {e.args[0]}"
                        )
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
                field_name_prefix=prefixed_field_name,
                avoid_subparsers=avoid_subparsers,
            )
            consumed_keywords |= consumed_keywords_child
        else:
            # Unions over dataclasses (subparsers). This is the only other option.
            assert len(parser_definition.subparsers_from_name) > 0
            assert prefixed_field_name in parser_definition.subparsers_from_name

            subparser_def = parser_definition.subparsers_from_name[prefixed_field_name]

            subparser_dest = _strings.make_subparser_dest(name=prefixed_field_name)
            consumed_keywords.add(subparser_dest)
            if subparser_dest in value_from_prefixed_field_name:
                subparser_name = get_value_from_arg(subparser_dest)
            else:
                assert subparser_def.default_instance not in _fields.MISSING_SINGLETONS
                default_instance = subparser_def.default_instance
                # assert default_instance is not None
                subparser_name = None

            if subparser_name is None:
                # No subparser selected -- this should only happen when we have a
                # default/default_factory set.
                assert (
                    type(None) in get_args(field_type)
                    or subparser_def.default_instance is not None
                )
                value = subparser_def.default_instance
            elif (
                subparser_def.can_be_none
                and subparser_name
                == _strings.subparser_name_from_type(prefixed_field_name, None)
            ):
                # do either
                # Optional[Union[A, B, ...]] or Union[A, B, None], or have a
                # default/default_factory set.
                value = None
            else:
                options = map(
                    lambda x: x if x not in type_from_typevar else type_from_typevar[x],
                    get_args(field_type),
                )
                chosen_f = None
                for option in options:
                    if (
                        _strings.subparser_name_from_type(prefixed_field_name, option)
                        == subparser_name
                    ):
                        chosen_f = option
                        break
                assert chosen_f is not None
                value, consumed_keywords_child = call_from_args(
                    chosen_f,
                    subparser_def.parser_from_name[subparser_name],
                    field.default if type(field.default) is chosen_f else None,
                    value_from_prefixed_field_name,
                    field_name_prefix=prefixed_field_name,
                    avoid_subparsers=avoid_subparsers,
                )
                consumed_keywords |= consumed_keywords_child

        if value is not _fields.EXCLUDE_FROM_CALL:
            if field.positional:
                args.append(value)
            else:
                kwargs[
                    field.name if field.name_override is None else field.name_override
                ] = value

    unwrapped_f = _resolver.unwrap_origin(f)
    unwrapped_f = list if unwrapped_f is Sequence else unwrapped_f  # type: ignore
    unwrapped_f = _resolver.narrow_type(unwrapped_f, default_instance)
    if unwrapped_f in (tuple, list, set):
        if len(args) == 0:
            # When tuples are used as nested structures (eg Tuple[SomeDataclass]), we
            # use keyword arguments.
            return unwrapped_f(kwargs.values()), consumed_keywords  # type: ignore
        else:
            # When tuples are directly parsed (eg Tuple[int, int]), we end up with a
            # single set of positional arguments.
            assert len(args) == 1
            return unwrapped_f(args[0]), consumed_keywords  # type: ignore
    elif unwrapped_f is dict:
        for arg in args:
            assert isinstance(arg, dict)
            kwargs.update(arg)
        return kwargs, consumed_keywords  # type: ignore
    else:
        return unwrapped_f(*args, **kwargs), consumed_keywords  # type: ignore
