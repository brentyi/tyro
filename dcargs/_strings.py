import functools
import re
import textwrap
from typing import Type

from . import _resolver

NESTED_DATACLASS_DELIMETER: str = "."
SUBPARSER_DEST_FMT: str = "{name} (positional)"


def dedent(text: str) -> str:
    """Same as textwrap.dedent, but ignores the first line."""
    first_line, line_break, rest = text.partition("\n")
    if line_break == "":
        return textwrap.dedent(text)
    return f"{first_line.strip()}\n{textwrap.dedent(rest)}"


_camel_separator_pattern = functools.lru_cache(maxsize=1)(
    lambda: re.compile("((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))")
)


def hyphen_separated_from_camel_case(name: str) -> str:
    return _camel_separator_pattern().sub(r"-\1", name).lower()


def subparser_name_from_type(cls: Type) -> str:
    cls, type_from_typevar = _resolver.resolve_generic_classes(cls)
    if len(type_from_typevar) == 0:
        assert hasattr(cls, "__name__")
        return hyphen_separated_from_camel_case(cls.__name__)  # type: ignore

    return "-".join(
        map(
            subparser_name_from_type,
            [cls] + list(type_from_typevar.values()),
        )
    )


def bool_from_string(text: str) -> bool:
    text = text.lower()
    if text in ("true", "1"):
        return True
    elif text in ("false", "0"):
        return False
    else:
        raise ValueError(f"Boolean (True/False or 1/0) expected, but got {text}.")
