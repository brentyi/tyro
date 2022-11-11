"""Utilities and constants for working with strings."""

import functools
import re
import textwrap
from typing import Iterable, List, Sequence, Tuple, Type, Union

from . import _resolver

dummy_field_name = "__tyro_dummy_field__"


def _strip_dummy_field_names(parts: Iterable[str]) -> Iterable[str]:
    return filter(lambda name: len(name) > 0 and name != dummy_field_name, parts)


def make_field_name(parts: Sequence[str]) -> str:
    """Join parts of a field name together. Used for nesting.

    ('parent_1', 'child') => 'parent-1.child'
    ('parents', '1', '_child_node') => 'parents.1._child-node'
    """
    out: List[str] = []
    for i, p in enumerate(_strip_dummy_field_names(parts)):
        if i > 0:
            out.append(".")

        # Replace all underscores with hyphens, except ones at the start of a string.
        num_underscore_prefix = 0
        for i in range(len(p)):
            if p[i] == "_":
                num_underscore_prefix += 1
            else:
                break
        p = "_" * num_underscore_prefix + p[num_underscore_prefix:].replace("_", "-")
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


def _subparser_name_from_type(cls: Type) -> Tuple[str, bool]:
    from .conf import _confstruct  # Prevent circular imports

    cls, type_from_typevar = _resolver.resolve_generic_types(cls)
    cls, found_subcommand_configs = _resolver.unwrap_annotated(
        cls, _confstruct._SubcommandConfiguration
    )

    # Subparser name from `tyro.metadata.subcommand()`.
    found_name = None
    prefix_name = True
    if len(found_subcommand_configs) > 0:
        found_name = found_subcommand_configs[0].name
        prefix_name = found_subcommand_configs[0].prefix_name

    if found_name is not None:
        return found_name, prefix_name

    # Subparser name from class name.
    if len(type_from_typevar) == 0:
        assert hasattr(cls, "__name__")
        return hyphen_separated_from_camel_case(cls.__name__), prefix_name  # type: ignore

    return (
        "-".join(
            map(
                lambda x: _subparser_name_from_type(x)[0],
                [cls] + list(type_from_typevar.values()),
            )
        ),
        prefix_name,
    )


def subparser_name_from_type(prefix: str, cls: Union[Type, None]) -> str:
    suffix, use_prefix = (
        _subparser_name_from_type(cls) if cls is not None else ("None", True)
    )
    if len(prefix) == 0 or not use_prefix:
        return suffix
    return f"{prefix}:{suffix}".replace("_", "-")


@functools.lru_cache(maxsize=None)
def _get_ansi_pattern() -> re.Pattern:
    # https://stackoverflow.com/a/14693789
    return re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi_sequences(x: str):
    return _get_ansi_pattern().sub("", x)


def multi_metavar_from_single(single: str) -> str:
    if len(strip_ansi_sequences(single)) >= 32:
        # Shorten long metavars
        return f"{single} [...]"
    else:
        return f"{single} [{single} ...]"


def remove_single_line_breaks(helptext: str) -> str:
    lines = helptext.split("\n")
    output_parts: List[str] = []
    for line in lines:
        # Remove trailing whitespace.
        line = line.rstrip()

        # Empty line.
        if len(line) == 0:
            prev_is_break = len(output_parts) >= 1 and output_parts[-1] == "\n"
            if not prev_is_break:
                output_parts.append("\n")
            output_parts.append("\n")

        # Empty line.
        else:
            if not line[0].isalpha():
                output_parts.append("\n")
            prev_is_break = len(output_parts) >= 1 and output_parts[-1] == "\n"
            if len(output_parts) >= 1 and not prev_is_break:
                output_parts.append(" ")
            output_parts.append(line)

    return "".join(output_parts).rstrip()  # type: ignore
