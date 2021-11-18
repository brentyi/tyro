import argparse
from typing import Optional, Sequence, Type, TypeVar, Union

from . import _construction, _parsers, _strings

DataclassType = TypeVar("DataclassType")


def parse(
    cls: Type[DataclassType],
    *,
    description: Optional[str] = None,
    args: Optional[Sequence[str]] = None,
) -> DataclassType:
    """Populate a dataclass via CLI args."""

    if description is None:
        description = ""

    parser_definition, construction_metadata = _parsers.ParserDefinition.from_dataclass(
        cls,
        parent_dataclasses=set(),  # Used for recursive calls.
        parent_type_from_typevar=None,  # Used for recursive calls.
        default_instance=None,  # Overrides for default values. This could also be exposed.
    )

    parser = argparse.ArgumentParser(
        description=_strings.dedent(description),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser_definition.apply(parser)

    namespace = parser.parse_args(args)

    value_from_arg = vars(namespace)
    out, consumed_keywords = _construction.construct_dataclass(
        cls, value_from_arg, construction_metadata
    )
    assert (
        consumed_keywords == value_from_arg.keys()
    ), "Not all arguments were consumed!"

    return out
