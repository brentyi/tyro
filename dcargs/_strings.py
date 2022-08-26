"""Utilities and constants for working with strings."""

import functools
import re
import textwrap
from typing import Iterable, List, Sequence, Type, Union

import termcolor

from . import _resolver

dummy_field_name = "__dcargs_dummy_field_name__"


def _strip_dummy_field_names(parts: Iterable[str]) -> Iterable[str]:
    return filter(lambda name: len(name) > 0 and name != dummy_field_name, parts)


def make_field_name(parts: Sequence[str]) -> str:
    """Join parts of a field name together. Used for nesting.

    ('parent', 'child') => 'parent.child'
    ('parents', '1', 'child') => 'parents:1.child'
    """
    out: List[str] = []
    for i, p in enumerate(_strip_dummy_field_names(parts)):
        if i > 0:
            out.append(".")

        out.append(p)

    return "".join(out)


def make_subparser_dest(name: str) -> str:
    return f"{name} (positional)"


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


def _subparser_name_from_type(cls: Type) -> str:
    cls, type_from_typevar = _resolver.resolve_generic_types(cls)
    if len(type_from_typevar) == 0:
        assert hasattr(cls, "__name__")
        return hyphen_separated_from_camel_case(cls.__name__)  # type: ignore

    return "-".join(
        map(
            _subparser_name_from_type,
            [cls] + list(type_from_typevar.values()),
        )
    )


def subparser_name_from_type(prefix: str, cls: Union[Type, None]) -> str:
    suffix = _subparser_name_from_type(cls) if cls is not None else "None"
    if len(prefix) == 0:
        return suffix
    return f"{prefix}:{suffix}"


@functools.lru_cache(maxsize=None)
def _get_ansi_pattern() -> re.Pattern:
    # https://stackoverflow.com/a/14693789
    return re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi_sequences(x: str):
    return _get_ansi_pattern().sub("", x)


def format_metavar(x: str) -> str:
    return termcolor.colored(x, attrs=["bold"])


def multi_metavar_from_single(single: str) -> str:
    if len(strip_ansi_sequences(single)) >= 32:
        # Shorten long metavars
        return f"{single} [...]"
    else:
        return f"{single} [{single} ...]"
