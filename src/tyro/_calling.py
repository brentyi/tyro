"""Core functionality for calling functions with arguments specified by argparse
namespaces."""

from __future__ import annotations

import dataclasses
import itertools
from functools import partial
from typing import Any, Callable, Dict, List, Set, Tuple, TypeVar, Union

from typing_extensions import get_args

from . import _arguments, _fields, _parsers, _resolver, _singleton, _strings
from .conf import _markers


@dataclasses.dataclass(frozen=True)
class InstantiationError(Exception):
    """Exception raised when instantiation fail; this typically means that values from
    the CLI are invalid."""

    message: str
    arg: Union[_arguments.ArgumentDefinition, str]


T = TypeVar("T")


def callable_with_args(
    f: Callable[..., T],
    parser_definition: _parsers.ParserSpecification,
    default_instance: Union[T, _singleton.NonpropagatingMissingType],
    value_from_prefixed_field_name: Dict[str, Any],
    field_name_prefix: str,
) -> Tuple[Callable[[], T], Set[str]]:
    """Populate `f` with arguments specified by a dictionary of values from argparse.

    Returns a partialed version of `f` with arguments populated, and a set of
    used arguments.

    We return a `Callable[[], OutT]` instead of `T` directly for aesthetic
    reasons; it lets use reduce layers in stack traces for errors from
    functions passed to `tyro`.
    """

    positional_args: List[Any] = []
    kwargs: Dict[str, Any] = {}
    consumed_keywords: Set[str] = set()

    def get_value_from_arg(prefixed_field_name: str) -> Any:
        """Helper for getting values from `value_from_arg` + doing some extra
        asserts."""
        assert (
            prefixed_field_name in value_from_prefixed_field_name
        ), f"{prefixed_field_name} not in {value_from_prefixed_field_name}"
        return value_from_prefixed_field_name[prefixed_field_name]

    arg_from_prefixed_field_name: Dict[str, _arguments.ArgumentDefinition] = {}
    for arg in parser_definition.args:
        arg_from_prefixed_field_name[
            _strings.make_field_name([arg.intern_prefix, arg.field.intern_name])
        ] = arg

    any_arguments_provided = False

    for field in parser_definition.field_list:
        value: Any
        prefixed_field_name = _strings.make_field_name(
            [field_name_prefix, field.intern_name]
        )

        # Resolve field type.
        field_type = field.type_stripped
        if prefixed_field_name in arg_from_prefixed_field_name:
            assert prefixed_field_name not in consumed_keywords

            # Standard arguments.
            arg = arg_from_prefixed_field_name[prefixed_field_name]
            name_maybe_prefixed = prefixed_field_name
            consumed_keywords.add(name_maybe_prefixed)
            if not arg.lowered.is_fixed():
                value = get_value_from_arg(name_maybe_prefixed)

                if value in _fields.MISSING_AND_MISSING_NONPROP:
                    value = arg.field.default

                    # Consider a function with a positional sequence argument:
                    #
                    #     def f(x: tuple[int, ...], /)
                    #
                    # If we run this script with no arguments, we should interpret this
                    # as empty input for x. But the argparse default will be a MISSING
                    # value, and the field default will be inspect.Parameter.empty.
                    if (
                        value in _fields.MISSING_AND_MISSING_NONPROP
                        and field.is_positional_call()
                        and arg.lowered.nargs in ("?", "*")
                    ):
                        value = []
                else:
                    any_arguments_provided = True
                    if arg.lowered.nargs == "?":
                        # Special case for optional positional arguments: this is the
                        # only time that arguments don't come back as a list.
                        value = [value]

                    try:
                        assert arg.lowered.instance_from_str is not None
                        value = arg.lowered.instance_from_str(value)
                    except (ValueError, TypeError) as e:
                        raise InstantiationError(
                            e.args[0],
                            arg,
                        )
            else:
                assert arg.field.default not in _fields.MISSING_AND_MISSING_NONPROP
                value = arg.field.default
                parsed_value = value_from_prefixed_field_name.get(prefixed_field_name)
                if parsed_value not in _fields.MISSING_AND_MISSING_NONPROP:
                    raise InstantiationError(
                        f"{arg.lowered.name_or_flag} was passed in, but"
                        " is a fixed argument that cannot be parsed",
                        arg,
                    )
        elif prefixed_field_name in parser_definition.child_from_prefix:
            # Nested callable.
            if _resolver.unwrap_origin_strip_extras(field_type) is Union:
                field_type = type(field.default)
            get_value, consumed_keywords_child = callable_with_args(
                field_type,
                parser_definition.child_from_prefix[prefixed_field_name],
                field.default,
                value_from_prefixed_field_name,
                field_name_prefix=prefixed_field_name,
            )
            value = get_value()
            del get_value
            consumed_keywords |= consumed_keywords_child
        else:
            # Unions over dataclasses (subparsers). This is the only other option.
            subparser_def = parser_definition.subparsers_from_intern_prefix[
                prefixed_field_name
            ]
            subparser_dest = _strings.make_subparser_dest(name=prefixed_field_name)
            consumed_keywords.add(subparser_dest)
            if subparser_dest in value_from_prefixed_field_name:
                subparser_name = get_value_from_arg(subparser_dest)
            else:
                assert (
                    subparser_def.default_instance
                    not in _fields.MISSING_AND_MISSING_NONPROP
                )
                subparser_name = None

            if subparser_name is None:
                # No subparser selected -- this should only happen when we have a
                # default/default_factory set.
                assert (
                    type(None) in get_args(field_type)
                    or subparser_def.default_instance is not None
                )
                value = subparser_def.default_instance
            else:
                chosen_f = subparser_def.options[
                    list(subparser_def.parser_from_name.keys()).index(subparser_name)
                ]
                get_value, consumed_keywords_child = callable_with_args(
                    chosen_f,
                    subparser_def.parser_from_name[subparser_name],
                    (
                        field.default
                        if type(field.default) is chosen_f
                        else _singleton.MISSING_NONPROP
                    ),
                    value_from_prefixed_field_name,
                    field_name_prefix=prefixed_field_name,
                )
                value = get_value()
                del get_value
                consumed_keywords |= consumed_keywords_child

        if value is _singleton.EXCLUDE_FROM_CALL:
            continue

        if _markers._UnpackArgsCall in field.markers:
            if len(positional_args) == 0 and len(kwargs) > 0:
                positional_args.extend(kwargs.values())
                kwargs.clear()
            assert isinstance(value, tuple)
            positional_args.extend(value)
        elif _markers._UnpackKwargsCall in field.markers:
            assert isinstance(value, dict)
            kwargs.update(value)
        elif field.is_positional_call():
            assert len(kwargs) == 0
            positional_args.append(value)
        else:
            kwargs[field.call_argname] = value

    # Logic for _markers._OPTIONAL_GROUP.
    is_missing_list = [
        any(v is m for m in _fields.MISSING_AND_MISSING_NONPROP)
        for v in itertools.chain(positional_args, kwargs.values())
    ]
    if any(is_missing_list):
        if not any_arguments_provided:
            # No arguments were provided in this group.
            return lambda: default_instance, consumed_keywords  # type: ignore

        message = "either all arguments must be provided or none of them."
        if len(kwargs) > 0:
            missing_args: List[str] = []
            for k, v in kwargs.items():
                if v not in _fields.MISSING_AND_MISSING_NONPROP:
                    break

                # Argument is missing.
                found = False
                for arg in arg_from_prefixed_field_name.values():
                    if arg.field.call_argname == k:
                        missing_args.append(arg.lowered.name_or_flag)
                        found = True
                        break
                assert found, "This is likely a bug in tyro."

            if len(missing_args):
                message += f" We're missing arguments {missing_args}."
        raise InstantiationError(
            message,
            field_name_prefix,
        )

    # Note: we unwrap types both before and after narrowing. This is because narrowing
    # sometimes produces types like `Tuple[T1, T2, ...]`, where we actually want just
    # `tuple`.
    unwrapped_f = f
    unwrapped_f = _resolver.swap_type_using_confstruct(unwrapped_f)
    unwrapped_f = _resolver.unwrap_origin_strip_extras(unwrapped_f)
    unwrapped_f = _resolver.narrow_subtypes(unwrapped_f, default_instance)
    unwrapped_f = _resolver.unwrap_origin_strip_extras(unwrapped_f)

    if unwrapped_f in (tuple, list, set):
        if len(positional_args) > 0:
            # Triggered when support_single_arg_types=True is used.
            assert len(kwargs) == 0
            assert len(positional_args) == 1
            return lambda: positional_args[0], consumed_keywords  # type: ignore
        else:
            assert len(positional_args) == 0
            return partial(unwrapped_f, kwargs.values()), consumed_keywords  # type: ignore
    elif unwrapped_f is dict:
        if len(positional_args) > 0:
            # Triggered when support_single_arg_types=True is used.
            assert len(kwargs) == 0
            assert len(positional_args) == 1
            return partial(unwrapped_f, *positional_args), consumed_keywords  # type: ignore
        else:
            assert len(positional_args) == 0
            return lambda: kwargs, consumed_keywords  # type: ignore
    else:
        if field_name_prefix == "":
            # Don't catch any errors for the "root" field. If main() in tyro.cli(main)
            # raises a ValueError, this shouldn't be caught.
            return partial(unwrapped_f, *positional_args, **kwargs), consumed_keywords  # type: ignore
        else:
            # Try to catch ValueErrors raised by field constructors.
            def with_instantiation_error():
                try:
                    return unwrapped_f(*positional_args, **kwargs)
                # If unwrapped_f raises a ValueError, wrap the message with a more informative
                # InstantiationError if possible.
                except ValueError as e:
                    raise InstantiationError(
                        e.args[0],
                        field_name_prefix,
                    )

            return with_instantiation_error, consumed_keywords  # type: ignore
