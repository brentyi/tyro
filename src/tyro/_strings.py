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
        stripped = p.lstrip("_")
        p = p[: len(p) - len(stripped)] + stripped.replace("_", "-")
    else:
        p = p.replace("-", "_")
    return p


def make_field_name(parts: Sequence[str]) -> str:
    """Join parts of a field name together. Used for nesting.

    ('parent_1', 'child') => 'parent-1.child'
    ('parents', '1', '_child_node') => 'parents.1._child-node'
    ('parents', '1', 'middle._child_node') => 'parents.1.middle._child-node'
    """
    out = ".".join(parts)
    return ".".join(
        replace_delimeter_in_part(part)
        for part in out.split(".")
        if len(part) > 0 and part != dummy_field_name
    )


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
    _, type_alias_breadcrumbs = _resolver.unwrap_annotated(
        cls, _resolver.TyroTypeAliasBreadCrumb
    )
    cls, found_subcommand_configs = _resolver.unwrap_annotated(
        cls, _confstruct._SubcommandConfig
    )

    # Subparser name from `tyro.conf.subcommand()`.
    found_name = None
    prefix_name = True
    if len(found_subcommand_configs) > 0:
        found_name = found_subcommand_configs[0].name
        prefix_name = found_subcommand_configs[0].prefix_name

    if found_name is not None:
        return found_name, prefix_name

    # Subparser name from type alias. This is lower priority thant he name from
    # `tyro.conf.subcommand()`.
    if len(type_alias_breadcrumbs) > 0:
        return (
            hyphen_separated_from_camel_case(type_alias_breadcrumbs[-1].name),
            prefix_name,
        )

    # Subparser name from class name.
    def get_name(cls: Type) -> str:
        orig = get_origin(cls)
        if orig is not None and hasattr(orig, "__name__"):
            parts = [orig.__name__]  # type: ignore
            parts.extend(map(get_name, get_args(cls)))
            parts = [hyphen_separated_from_camel_case(part) for part in parts]
            return get_delimeter().join(parts)
        elif hasattr(cls, "__name__"):
            return hyphen_separated_from_camel_case(cls.__name__)
        else:
            return hyphen_separated_from_camel_case(str(cls))

    if len(type_from_typevar) == 0:
        return get_name(cls), prefix_name  # type: ignore

    return (
        get_delimeter().join(
            [get_name(cls)]
            + list(
                map(
                    lambda x: _subparser_name_from_type(x)[0],
                    list(type_from_typevar.values()),
                )
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


def join_union_metavars(metavars: Iterable[str]) -> str:
    """Metavar generation helper for unions. Could be revisited.

    Examples:
        None, INT => NONE|INT
        {0,1,2}, {3,4} => {0,1,2,3,4}
        {0,1,2}, {3,4}, STR => {0,1,2,3,4}|STR
        {None}, INT [INT ...] => {None}|{INT [INT ...]}
        STR, INT [INT ...] => STR|{INT [INT ...]}
        STR, INT INT => STR|{INT INT}

    The curly brackets are unfortunately overloaded but alternatives all interfere with
    argparse internals.
    """
    metavars = tuple(metavars)
    merged_metavars = [metavars[0]]
    for i in range(1, len(metavars)):
        prev = merged_metavars[-1]
        curr = metavars[i]
        if (
            prev.startswith("{")
            and prev.endswith("}")
            and curr.startswith("{")
            and curr.endswith("}")
        ):
            merged_metavars[-1] = prev[:-1] + "," + curr[1:]
        else:
            merged_metavars.append(curr)

    for i, m in enumerate(merged_metavars):
        if " " in m:
            merged_metavars[i] = "{" + m + "}"

    return "|".join(merged_metavars)


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
