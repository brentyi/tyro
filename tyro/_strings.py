"""Utilities and constants for working with strings."""

import contextlib
import functools
import re
import textwrap
from typing import Iterable, List, Sequence, Tuple, Type

from typing_extensions import Literal, get_args, get_origin

from . import _resolver

dummy_field_name = "__tyro_dummy_field__"
DELIMETER: Literal["-", "_"] = "-"


def _strip_dummy_field_names(parts: Iterable[str]) -> Iterable[str]:
    return filter(lambda name: len(name) > 0 and name != dummy_field_name, parts)


@contextlib.contextmanager
def delimeter_context(delimeter: Literal["-", "_"]):
    """Context for setting the delimeter. Determines if `field_a` is populated as
    `--field-a` or `--field_a`. Not thread-safe."""
    global DELIMETER
    delimeter_restore = DELIMETER
    DELIMETER = delimeter
    yield
    DELIMETER = delimeter_restore


def get_delimeter() -> Literal["-", "_"]:
    """Get delimeter used to separate words."""
    return DELIMETER


def replace_delimeter_in_part(p: str) -> str:
    """Replace hyphens with underscores (or vice versa) except when at the start."""
    if get_delimeter() == "-":
        num_underscore_prefix = 0
        for i in range(len(p)):
            if p[i] == "_":
                num_underscore_prefix += 1
            else:
                break
        p = "_" * num_underscore_prefix + (p[num_underscore_prefix:].replace("_", "-"))
    else:
        p = p.replace("-", "_")
    return p


def make_field_name(parts: Sequence[str]) -> str:
    """Join parts of a field name together. Used for nesting.

    ('parent_1', 'child') => 'parent-1.child'
    ('parents', '1', '_child_node') => 'parents.1._child-node'
    ('parents', '1', 'middle._child_node') => 'parents.1.middle._child-node'
    """
    out: List[str] = []
    for p in _strip_dummy_field_names(parts):
        out.extend(map(replace_delimeter_in_part, p.split(".")))
    return ".".join(out)


def make_subparser_dest(name: str) -> str:
    return f"{name} (positional)"


def dedent(text: str) -> str:
    """Same as textwrap.dedent, but ignores the first line."""
    first_line, line_break, rest = text.partition("\n")
    if line_break == "":
        return textwrap.dedent(text)
    return f"{first_line.strip()}\n{textwrap.dedent(rest)}"


def hyphen_separated_from_camel_case(name: str) -> str:
    out = (
        re.compile("((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))")
        .sub(get_delimeter() + r"\1", name)
        .lower()
    )
    return out


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
    def get_name(cls: Type) -> str:
        orig = get_origin(cls)
        if orig is not None and hasattr(orig, "__name__"):
            parts = [orig.__name__]  # type: ignore
            parts.extend(map(get_name, get_args(cls)))
            return get_delimeter().join(parts)
        elif hasattr(cls, "__name__"):
            return hyphen_separated_from_camel_case(cls.__name__)
        else:
            raise AssertionError(
                f"Tried to interpret {cls} as a subcommand, but could not infer name"
            )

    if len(type_from_typevar) == 0:
        return get_name(cls), prefix_name  # type: ignore

    return (
        get_delimeter().join(
            map(
                lambda x: _subparser_name_from_type(x)[0],
                [cls] + list(type_from_typevar.values()),
            )
        ),
        prefix_name,
    )


def subparser_name_from_type(prefix: str, cls: Type) -> str:
    suffix, use_prefix = (
        _subparser_name_from_type(cls) if cls is not type(None) else ("None", True)
    )
    if len(prefix) == 0 or not use_prefix:
        return suffix

    if get_delimeter() == "-":
        return f"{prefix}:{make_field_name(suffix.split('.'))}"
    else:
        assert get_delimeter() == "_"
        return f"{prefix}:{suffix}"


@functools.lru_cache(maxsize=None)
def _get_ansi_pattern() -> re.Pattern:
    # https://stackoverflow.com/a/14693789
    return re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi_sequences(x: str):
    return _get_ansi_pattern().sub("", x)


def multi_metavar_from_single(single: str) -> str:
    if len(strip_ansi_sequences(single)) >= 32:
        # Shorten long metavars
        return f"[{single} [...]]"
    else:
        return f"[{single} [{single} ...]]"


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
