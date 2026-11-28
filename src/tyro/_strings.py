"""Utilities and constants for working with strings."""

import _thread
import functools
import re
from typing import Iterable, List, Literal, Tuple, Type

from typing_extensions import get_args, get_origin

from tyro._typing_compat import is_typing_union

from . import _resolver


class _DelimiterState(_thread._local):
    """Delimiter setting, which isn't shared between threads."""

    delimiter: Literal["-", "_"] = "-"


_state = _DelimiterState()


class delimiter_context:
    """Context for setting the delimiter. Determines if `field_a` is populated as
    `--field-a` or `--field_a`."""

    def __init__(self, delimiter: Literal["-", "_"]) -> None:
        self._delimiter: Literal["-", "_"] = delimiter

    def __enter__(self) -> None:
        self._delimiter_restore: Literal["-", "_"] = _state.delimiter
        _state.delimiter = self._delimiter

    def __exit__(self, *_: object) -> None:
        _state.delimiter = self._delimiter_restore


def get_delimiter() -> Literal["-", "_"]:
    """Get delimiter used to separate words."""
    return _state.delimiter


def swap_delimiters(p: str) -> str:
    """Replace hyphens with underscores (or vice versa) except when at the start or end."""
    if ("_" if _state.delimiter == "-" else "-") not in p:
        # Nothing to replace.
        return p
    if get_delimiter() == "-":
        left_stripped = p.lstrip("_")
        right_stripped = left_stripped.rstrip("_")
        prefix = p[: len(p) - len(left_stripped)]
        suffix = left_stripped[len(right_stripped) :]
        p = prefix + right_stripped.replace("_", "-") + suffix
    else:
        left_stripped = p.lstrip("-")
        right_stripped = left_stripped.rstrip("-")
        prefix = p[: len(p) - len(left_stripped)]
        suffix = left_stripped[len(right_stripped) :]
        p = prefix + right_stripped.replace("-", "_") + suffix
    return p


def swap_delimiters_in_field_name(field_name: str) -> str:
    """Swap delimiters while preserving the edges of each dotted field component.

    Unlike ``make_field_name()``, preserve empty components so unknown option names
    are not collapsed into valid ones.
    """
    return _swap_delimiters_in_field_name(field_name, _state.delimiter)


@functools.lru_cache(maxsize=4096)
def _swap_delimiters_in_field_name(field_name: str, delimiter: str) -> str:
    # `delimiter` is only used as a cache key.
    del delimiter
    return ".".join([swap_delimiters(part) for part in field_name.split(".")])


def make_field_name(parts: Iterable[str]) -> str:
    """Join parts of a field name together. Used for nesting.

    ('parent_1', 'child') => 'parent-1.child'
    ('parents', '1', '_child_node') => 'parents.1._child-node'
    ('parents', '1', 'middle._child_node') => 'parents.1.middle._child-node'
    """
    return _make_field_name(".".join(parts), _state.delimiter)


@functools.lru_cache(maxsize=4096)
def _make_field_name(joined: str, delimiter: str) -> str:
    # `delimiter` is only used as a cache key.
    del delimiter
    return ".".join(
        swap_delimiters(part) for part in joined.split(".") if len(part) > 0
    )


def make_subparser_dest(name: str) -> str:
    return f"{name} (positional)"


def dedent(text: str) -> str:
    """Same as textwrap.dedent, but ignores the first line."""
    import textwrap

    first_line, line_break, rest = text.partition("\n")
    if line_break == "":
        return textwrap.dedent(text)
    return f"{first_line.strip()}\n{textwrap.dedent(rest)}"


def hyphen_separated_from_camel_case(name: str) -> str:
    out = re.sub(
        "((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))", get_delimiter() + r"\1", name
    ).lower()
    return out


def _subparser_name_from_type(cls: Type) -> Tuple[str, bool]:
    from .conf import _confstruct  # Prevent circular imports

    # Subparser name from `tyro.conf.subcommand()`.
    prefix_name = True
    _, annotations = _resolver.unwrap_annotated(cls, "all")
    for x in annotations:
        if isinstance(x, _confstruct._SubcommandConfig):
            prefix_name = x.prefix_name
            if x.name is not None:
                return x.name, prefix_name
            break

    cls, type_from_typevar = _resolver.resolve_generic_types(cls)

    # Configuration objects can also be attached to the origin of a generic type, using
    # the `@tyro.conf.configure()` decorator.
    _, annotations = _resolver.unwrap_annotated(cls, "all")
    for x in annotations:
        if isinstance(x, _confstruct._SubcommandConfig):
            prefix_name = x.prefix_name
            if x.name is not None:
                return x.name, prefix_name
            break

    _, type_alias_breadcrumbs = _resolver.unwrap_annotated(
        cls, _resolver.TyroTypeAliasBreadCrumb
    )
    cls = _resolver.unwrap_annotated(cls)

    # Subparser name from type alias. This is lower priority than the name from
    # `tyro.conf.subcommand()`.
    if len(type_alias_breadcrumbs) > 0:
        return (
            hyphen_separated_from_camel_case(type_alias_breadcrumbs[-1].name),
            prefix_name,
        )

    # Subparser name from class name.
    def get_name(cls: Type) -> str:
        orig = get_origin(cls)

        # Handle _SpecialForm version of Union, which doesn't have __name__,
        # normalize UnionType to Union, etc.
        orig_name: str | None
        if is_typing_union(orig):
            orig_name = "Union"
        else:
            orig_name = getattr(orig, "__name__", None)

        if orig_name is not None:
            parts = [orig_name]  # type: ignore
            parts.extend(map(get_name, get_args(cls)))
            parts = [hyphen_separated_from_camel_case(part) for part in parts]
            return get_delimiter().join(parts)
        elif hasattr(cls, "__name__"):
            return hyphen_separated_from_camel_case(cls.__name__)
        else:
            return hyphen_separated_from_camel_case(str(cls))

    if len(type_from_typevar) == 0:
        return get_name(cls), prefix_name  # type: ignore

    return (
        get_delimiter().join(
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
        _subparser_name_from_type(cls) if cls is not type(None) else ("none", True)
    )
    if len(prefix) == 0 or not use_prefix:
        return suffix

    if get_delimiter() == "-":
        return f"{prefix}:{make_field_name(suffix.split('.'))}"
    else:
        assert get_delimiter() == "_"
        return f"{prefix}:{suffix}"


@functools.lru_cache(maxsize=None)
def _get_ansi_pattern() -> re.Pattern:
    # https://stackoverflow.com/a/14693789
    return re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi_sequences(x: str):
    return _get_ansi_pattern().sub("", x)


_SHELL_SAFE_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_@%+=:,./-"
)


def shell_quote(x: str) -> str:
    """Same as `shlex.quote()`. Only imports `shlex` when it's needed."""
    if len(x) > 0 and _SHELL_SAFE_CHARS.issuperset(x):
        return x

    import shlex

    return shlex.quote(x)


def multi_metavar_from_single(single: str) -> str:
    if len(single) >= 32:
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
        # Only merge curly brace expressions that represent literal choices (contain commas).
        # Don't merge if either contains spaces (indicating tuples/sequences) or nested braces.
        if (
            prev.startswith("{")
            and prev.endswith("}")
            and curr.startswith("{")
            and curr.endswith("}")
            and " " not in prev
            and " " not in curr
            and "{" not in prev[1:-1]
            and "{" not in curr[1:-1]
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

        # Non-empty line.
        else:
            if len(output_parts) > 0 and not line[0].isalpha():
                output_parts.append("\n")
            prev_is_break = len(output_parts) >= 1 and output_parts[-1] == "\n"
            if len(output_parts) >= 1 and not prev_is_break:
                output_parts.append(" ")
            output_parts.append(line)

    return "".join(output_parts).rstrip()  # type: ignore
