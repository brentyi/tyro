"""Utilities and constants for working with strings."""

import functools
import re
import textwrap
from typing import List, Sequence, Type

from . import _resolver


def make_field_name(parts: Sequence[str]) -> str:
    """Join parts of a field name together. Used for nesting.

    ('parent', 'child') => 'parent.child'
    ('parents', '1', 'child') => 'parents:1.child'
    """
    out: List[str] = []
    for i, p in enumerate([p for p in parts if len(p) > 0]):
        if i > 0:
            # Delimeter between parts. We use a colon before integers, which can
            # currently only come from indices! (since field names can't start with
            # digits)
            out.append(":" if p[0].isdigit() else ".")

        out.append(p)

    return "".join(out)


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
    cls, type_from_typevar = _resolver.resolve_generic_types(cls)
    if len(type_from_typevar) == 0:
        assert hasattr(cls, "__name__")
        return hyphen_separated_from_camel_case(cls.__name__)  # type: ignore

    return "-".join(
        map(
            subparser_name_from_type,
            [cls] + list(type_from_typevar.values()),
        )
    )


@functools.lru_cache(maxsize=None)
def _get_ansi_pattern() -> re.Pattern:
    # https://stackoverflow.com/a/14693789
    return re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi_sequences(x: str):
    return _get_ansi_pattern().sub("", x)
