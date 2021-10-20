import argparse
from typing import Optional, Sequence, Type, TypeVar, Union

from typing_extensions import _GenericAlias  # type: ignore

from . import _construction, _parsers, _strings

DataclassType = TypeVar("DataclassType", bound=Union[Type, _GenericAlias])


def parse(
    cls: Type[DataclassType],
    description: str = "",
    args: Optional[Sequence[str]] = None,
) -> DataclassType:
    """Populate a dataclass via CLI args."""

    parser_definition, construction_metadata = _parsers.ParserDefinition.from_dataclass(
        cls,
        parent_dataclasses=set(),  # Used for recursive calls.
        subparser_name_from_type={},  # Aliases for subparsers; this is working, but not yet exposed.
        parent_type_from_typevar=None,  # Used for recursive calls.
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
