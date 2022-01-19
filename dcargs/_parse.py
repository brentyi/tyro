import argparse
from typing import Optional, Sequence, Type, TypeVar

from . import _construction, _parsers, _strings

DataclassType = TypeVar("DataclassType")


def parse(
    cls: Type[DataclassType],
    *,
    description: Optional[str] = None,
    args: Optional[Sequence[str]] = None,
) -> DataclassType:
    """Populate a dataclass via CLI args."""

    # Map a dataclass to the relevant CLI arguments + subparsers.
    parser_definition = _parsers.ParserSpecification.from_dataclass(
        cls,
        parent_dataclasses=set(),  # Used for recursive calls.
        parent_type_from_typevar=None,  # Used for recursive calls.
        default_instance=None,  # Overrides for default values. This could also be exposed.
    )

    # Parse using argparse!
    parser = argparse.ArgumentParser(
        description="" if description is None else _strings.dedent(description),
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
