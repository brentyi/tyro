"""Completion specification format and serialization.

This module defines the JSON-serializable completion spec format used by
the embedded Python completion logic in bash/zsh scripts.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Union, get_args, get_origin

if sys.version_info >= (3, 11):
    from typing import NotRequired, TypedDict
else:
    from typing_extensions import NotRequired, TypedDict

from ... import _arguments, _parsers, _typing_compat
from ...conf import _markers
from ...constructors._primitive_spec import UnsupportedTypeAnnotationError


class OptionSpec(TypedDict):
    """Specification for a single CLI option."""

    flags: List[str]
    """Option flags (e.g., ["-h", "--help"] or ["--config"])."""
    description: str
    """Human-readable description shown in completions."""
    type: str
    """Option type: "flag", "value", "choice", "boolean", or "path"."""
    cascade: NotRequired[bool]
    """Whether this option cascades to subcommands."""
    nargs: NotRequired[Union[int, str, None]]
    """Number of arguments (e.g., None, "?", "*", "+", or an int)."""
    choices: NotRequired[List[str]]
    """Valid choices when type is "choice"."""


class SubcommandSpec(TypedDict):
    """Specification for a subcommand and its nested structure."""

    description: str
    """Human-readable description of the subcommand."""
    options: List[OptionSpec]
    """Options available for this subcommand."""
    subcommands: Dict[str, SubcommandSpec]
    """Nested subcommands, keyed by name."""
    frontier_groups: List[List[str]]
    """Groups of mutually exclusive subcommand choices.

    When multiple independent subcommand selections exist at this level (e.g.,
    choosing both a model AND an optimizer), each inner list represents one
    group of mutually exclusive choices. The completion system uses this to
    track which groups have been satisfied and which still need selection.

    Empty when there's only one subcommand group (standard subcommands).
    """


class CompletionSpec(TypedDict):
    """Root completion specification for a CLI program."""

    prog: str
    """Program name."""
    options: List[OptionSpec]
    """Top-level options."""
    subcommands: Dict[str, SubcommandSpec]
    """Top-level subcommands, keyed by name."""
    frontier_groups: List[List[str]]
    """Groups of mutually exclusive subcommand choices at the root level.

    See SubcommandSpec.frontier_groups for detailed explanation.
    """


def build_completion_spec(
    parser_spec: _parsers.ParserSpecification,
    prog: str,
) -> CompletionSpec:
    """Build a completion specification from a ParserSpecification.

    Args:
        parser_spec: Parser specification to convert.
        prog: Program name.

    Returns:
        Completion spec for the CLI program.
    """
    spec: CompletionSpec = {
        "prog": prog,
        "options": _build_options(parser_spec),
        "subcommands": {},
        "frontier_groups": [],
    }

    # Build subcommands.
    subcommand_groups: List[List[str]] = []
    for _, subparsers_spec in sorted(
        parser_spec.subparsers_from_intern_prefix.items(),
        key=lambda item: item[0],
    ):
        group: List[str] = []
        for name, sub_spec_lazy in sorted(subparsers_spec.parser_from_name.items()):
            group.append(name)
            sub_spec = (
                sub_spec_lazy.evaluate()
                if isinstance(sub_spec_lazy, _parsers.LazyParserSpecification)
                else sub_spec_lazy
            )
            # Error should have been caught earlier.
            assert not isinstance(sub_spec, UnsupportedTypeAnnotationError), (
                "Unexpected UnsupportedTypeAnnotationError in backend"
            )
            spec["subcommands"][name] = _build_subcommand_spec(sub_spec, name)

        if group:
            subcommand_groups.append(group)

    # If we have multiple subparser groups, this is a frontier.
    if len(subcommand_groups) > 1:
        spec["frontier_groups"] = subcommand_groups

    return spec


def _build_subcommand_spec(
    parser_spec: _parsers.ParserSpecification,
    name: str,
) -> SubcommandSpec:
    """Build completion spec for a subcommand.

    Args:
        parser_spec: Parser specification for the subcommand.
        name: Name of the subcommand.

    Returns:
        Subcommand spec.
    """
    spec: SubcommandSpec = {
        "description": name.replace(":", " "),
        "options": _build_options(parser_spec),
        "subcommands": {},
        "frontier_groups": [],
    }

    # Build nested subcommands.
    subcommand_groups: List[List[str]] = []
    for _, subparsers_spec in sorted(
        parser_spec.subparsers_from_intern_prefix.items(),
        key=lambda item: item[0],
    ):
        group: List[str] = []
        for sub_name, sub_spec_lazy in sorted(subparsers_spec.parser_from_name.items()):
            group.append(sub_name)
            sub_spec = (
                sub_spec_lazy.evaluate()
                if isinstance(sub_spec_lazy, _parsers.LazyParserSpecification)
                else sub_spec_lazy
            )
            # Error should have been caught earlier.
            assert not isinstance(sub_spec, UnsupportedTypeAnnotationError), (
                "Unexpected UnsupportedTypeAnnotationError in backend"
            )
            spec["subcommands"][sub_name] = _build_subcommand_spec(sub_spec, sub_name)

        if group:
            subcommand_groups.append(group)

    if len(subcommand_groups) > 1:
        spec["frontier_groups"] = subcommand_groups

    return spec


def _build_options(parser_spec: _parsers.ParserSpecification) -> List[OptionSpec]:
    """Build option specifications from a parser.

    Args:
        parser_spec: Parser specification to extract options from.

    Returns:
        List of option specs.
    """
    options: List[OptionSpec] = []

    # Add help option.
    options.append(
        {
            "flags": ["-h", "--help"],
            "description": "show help message and exit",
            "type": "flag",
        }
    )

    for arg_with_ctx in parser_spec.get_args_including_children():
        arg = arg_with_ctx.arg
        lowered = arg.lowered
        if arg.is_positional() or lowered.is_fixed():
            continue

        # Determine option type and choices.
        option_type = "value"
        choices: List[str] | None = None

        origin = get_origin(arg.field.normalized_type.type)
        args = get_args(arg.field.normalized_type.type)
        if lowered.choices:
            option_type = "choice"
            choices = list(lowered.choices)
        elif lowered.action in ("store_true", "store_false", "count"):
            option_type = "flag"
        elif lowered.action == "boolean_optional_action":
            option_type = "boolean"
        elif arg.field.normalized_type.type in (str, Path) or (
            _typing_compat.is_typing_union(origin) and (str in args or Path in args)
        ):
            option_type = "path"

        # Check for cascade support.
        has_cascade = (
            _markers.CascadeSubcommandArgs in arg.field.normalized_type.markers
        )

        for flag in lowered.name_or_flags:
            # Build description from metavar + help text.
            # The metavar shows the type (e.g., INT, STR).
            metavar = (
                lowered.metavar if option_type not in ("flag", "boolean") else None
            )
            # Evaluate lazy help if callable.
            help_text = lowered.help
            if callable(help_text):
                help_text = help_text()
            helptext = help_text.strip() if help_text is not None else ""
            if metavar is None:
                description = helptext
            elif len(helptext) == 0:
                # This branch is currently never hit because tyro always generates
                # help text (e.g., "(default: ...)", "(required)", etc.).
                description = metavar  # pragma: no cover
            else:
                description = f"{metavar} • {helptext}"

            # Handle boolean optional action (--flag and --no-flag).
            flags = [flag]
            if option_type == "boolean":
                flags.append(_arguments.flag_to_inverse(flag))

            option_spec: OptionSpec = {
                "flags": flags,
                "description": description,
                "type": option_type,
                "cascade": has_cascade,
                "nargs": lowered.nargs,
            }
            if choices is not None:
                option_spec["choices"] = choices

            options.append(option_spec)

    return options
