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

    parser_definition = _parsers.ParserDefinition.from_dataclass(
        cls, parent_dataclasses=set()
    )

    parser = argparse.ArgumentParser(
        description=_strings.dedent(description),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser_definition.apply(parser)
    namespace = parser.parse_args(args)

    return _construction.construct_dataclass(
        cls, parser_definition.role_from_field, vars(namespace)
    )
