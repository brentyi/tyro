import argparse
from typing import Optional, Sequence, Type, TypeVar

from . import _construction, _docstrings, _parsers, _strings

DataclassType = TypeVar("DataclassType")


def parse(
    cls: Type[DataclassType],
    *,
    description: Optional[str] = None,
    args: Optional[Sequence[str]] = None,
    default_instance: Optional[DataclassType] = None,
) -> DataclassType:
    """Generate a CLI containing fields for a dataclass, and use it to create an
    instance of the class. Gracefully handles nested dataclasses, container types,
    generics, optional and default arguments, enums, and more.

    Args:
        cls: Dataclass type to instantiate.

    Keyword Args:
        description: Description text for the parser, displayed when the --help flag is
            passed in. If not specified, the dataclass docstring is used. Mirrors argument
            from `argparse.ArgumentParser()`.
        args: If set, parse arguments from a sequence of strings instead of the
            commandline. Mirrors argument from `argparse.ArgumentParser.parse_args()`.
        default_instance: An instance of `T` to use for default values. Helpful for overriding fields
            in an existing instance; if not specified, the field defaults are used instead.

    Returns:
        Instantiated dataclass.
    """
    # Map a dataclass to the relevant CLI arguments + subparsers.
    parser_definition = _parsers.ParserSpecification.from_dataclass(
        cls,
        parent_dataclasses=set(),  # Used for recursive calls.
        parent_type_from_typevar=None,  # Used for recursive calls.
        default_instance=default_instance,  # Overrides for default values.
    )

    if description is None:
        description = _docstrings.get_dataclass_docstring(cls)

    # Parse using argparse!
    parser = argparse.ArgumentParser(
        description=_strings.dedent(description),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser_definition.apply(parser)
    value_from_arg = vars(parser.parse_args(args=args))

    try:
        # Attempt to construct a dataclass from whatever was passed in.
        out, consumed_keywords = _construction.construct_dataclass(
            cls, parser_definition, value_from_arg
        )
    except _construction.FieldActionValueError as e:
        # Emulate argparse's error behavior when invalid arguments are passed in.
        parser.print_usage()
        print()
        print(e.args[0])
        raise SystemExit()

    assert consumed_keywords == value_from_arg.keys()
    return out
