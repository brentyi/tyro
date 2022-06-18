import argparse
from typing import Callable, Optional, Sequence, TypeVar

from . import _calling, _docstrings, _parsers, _resolver, _strings

T = TypeVar("T")


def cli(
    f: Callable[..., T],
    *,
    description: Optional[str] = None,
    args: Optional[Sequence[str]] = None,
    default_instance: Optional[T] = None,
) -> T:
    """Call `f(...)`, with arguments populated from an automatically generated CLI
    interface.

    `f` should have type-annotated inputs, and can be a function, class, or dataclass.
    Note that if `f` is a class, `dcargs.parse()` returns an instance.

    The parser is generated by populating helptext from docstrings and types from
    annotations; a broad range of core type annotations are supported...
        - Types natively accepted by `argparse`: str, int, float, pathlib.Path, etc.
        - Default values for optional parameters.
        - Booleans, which are automatically converted to flags when provided a default
          value.
        - Enums (via `enum.Enum`).
        - Various container types. Some examples:
          - `typing.ClassVar`.
          - `typing.Optional`.
          - `typing.Literal`.
          - `typing.Sequence`.
          - `typing.List`.
          - `typing.Tuple` types, such as `typing.Tuple[T1, T2, T3]` or
            `typing.Tuple[T, ...]`.
          - `typing.Set` types.
          - `typing.Final` types and `typing.Annotated`.
          - Nested combinations of the above: `Optional[Literal[T]]`,
            `Final[Optional[Sequence[T]]]`, etc.
        - Nested dataclasses.
          - Simple nesting.
          - Unions over nested dataclasses (subparsers).
          - Optional unions over nested dataclasses (optional subparsers).
        - Generic dataclasses (including nested generics).

    Args:
        f: Callable.

    Keyword Args:
        description: Description text for the parser, displayed when the --help flag is
            passed in. If not specified, the dataclass docstring is used. Mirrors argument
            from `argparse.ArgumentParser()`.
        args: If set, parse arguments from a sequence of strings instead of the
            commandline. Mirrors argument from `argparse.ArgumentParser.parse_args()`.
        default_instance: An instance of `T` to use for default values; only supported
            if `T` is a dataclass type. Helpful for merging CLI arguments with values loaded
            from elsewhere. (for example, a config object loaded from a yaml file)

    Returns:
        The output of `f(...)`.
    """

    # Map a callable to the relevant CLI arguments + subparsers.
    assert default_instance is None or _resolver.is_dataclass(
        f
    ), "Default instance specification is only supported for dataclasses!"
    parser_definition = _parsers.ParserSpecification.from_callable(
        f,
        parent_classes=set(),  # Used for recursive calls.
        parent_type_from_typevar=None,  # Used for recursive calls.
        default_instance=default_instance,  # Overrides for default values.
    )

    if description is None:
        description = _docstrings.get_callable_description(f)

    # Parse using argparse!
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser_definition.apply(parser)
    value_from_arg = vars(parser.parse_args(args=args))

    try:
        # Attempt to call `f` using whatever was passed in.
        out, consumed_keywords = _calling.call_from_args(
            f, parser_definition, value_from_arg
        )
    except _calling.FieldActionValueError as e:
        # Emulate argparse's error behavior when invalid arguments are passed in.
        parser.print_usage()
        print()
        print(e.args[0])
        raise SystemExit()

    assert consumed_keywords == value_from_arg.keys()
    return out
