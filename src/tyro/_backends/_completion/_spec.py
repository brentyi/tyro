"""Completion specification format and serialization.

This module defines the JSON-serializable completion spec format used by
the embedded Python completion logic in bash/zsh scripts.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ... import _arguments, _parsers


def build_completion_spec(
    parser_spec: _parsers.ParserSpecification,
    prog: str,
) -> Dict[str, Any]:
    """Build a completion specification from a ParserSpecification.

    Args:
        parser_spec: Parser specification to convert.
        prog: Program name.

    Returns:
        Dictionary representing the completion spec.
    """
    spec: Dict[str, Any] = {
        "prog": prog,
        "options": _build_options(parser_spec),
        "subcommands": {},
        "frontier_groups": [],
    }

    # Build subcommands.
    subcommand_groups: List[List[str]] = []
    for subparser_prefix, subparsers_spec in sorted(
        parser_spec.subparsers_from_intern_prefix.items()
    ):
        group: List[str] = []
        for name, sub_spec_lazy in sorted(subparsers_spec.parser_from_name.items()):
            group.append(name)
            sub_spec = (
                sub_spec_lazy.evaluate()
                if isinstance(sub_spec_lazy, _parsers.LazyParserSpecification)
                else sub_spec_lazy
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
) -> Dict[str, Any]:
    """Build completion spec for a subcommand.

    Args:
        parser_spec: Parser specification for the subcommand.
        name: Name of the subcommand.

    Returns:
        Dictionary representing the subcommand spec.
    """
    spec: Dict[str, Any] = {
        "description": name.replace(":", " "),
        "options": _build_options(parser_spec),
        "subcommands": {},
        "frontier_groups": [],
    }

    # Build nested subcommands.
    subcommand_groups: List[List[str]] = []
    for subparser_prefix, subparsers_spec in sorted(
        parser_spec.subparsers_from_intern_prefix.items()
    ):
        group: List[str] = []
        for sub_name, sub_spec_lazy in sorted(subparsers_spec.parser_from_name.items()):
            group.append(sub_name)
            sub_spec = (
                sub_spec_lazy.evaluate()
                if isinstance(sub_spec_lazy, _parsers.LazyParserSpecification)
                else sub_spec_lazy
            )
            spec["subcommands"][sub_name] = _build_subcommand_spec(sub_spec, sub_name)

        if group:
            subcommand_groups.append(group)

    if len(subcommand_groups) > 1:
        spec["frontier_groups"] = subcommand_groups

    return spec


def _build_options(parser_spec: _parsers.ParserSpecification) -> List[Dict[str, Any]]:
    """Build option specifications from a parser.

    Args:
        parser_spec: Parser specification to extract options from.

    Returns:
        List of option dictionaries.
    """
    options: List[Dict[str, Any]] = []

    # Add help option.
    options.append(
        {
            "flags": ["-h", "--help"],
            "description": "show help message and exit",
            "type": "flag",
        }
    )

    for arg in parser_spec.args:
        lowered = arg.lowered
        if arg.is_positional() or lowered.is_fixed():
            continue

        # Determine option type.
        option_type = "value"
        extra_data: Dict[str, Any] = {}

        if lowered.choices:
            option_type = "choice"
            extra_data["choices"] = list(lowered.choices)
        elif lowered.action in ("store_true", "store_false", "count"):
            option_type = "flag"
        elif lowered.action == "boolean_optional_action":
            option_type = "boolean"
        elif _is_path_argument(arg):
            option_type = "path"
            extra_data["is_directory"] = _is_directory_argument(arg)

        # Check for cascade support.
        has_cascade = _has_cascade_marker(arg)

        for flag in lowered.name_or_flags:
            # Build description from metavar + help text.
            # The metavar shows the type (e.g., INT, STR).
            metavar = (
                lowered.metavar if option_type not in ("flag", "boolean") else None
            )
            helptext = lowered.help.strip() if lowered.help is not None else ""
            if metavar is None:
                description = helptext
            elif len(helptext) == 0:
                # This branch is currently never hit because tyro always generates
                # help text (e.g., "(default: ...)", "(required)", etc.).
                description = metavar  # pragma: no cover
            else:
                description = f"{metavar} • {helptext}"

            option_dict: Dict[str, Any] = {
                "flags": [flag],
                "description": description,
                "type": option_type,
                "cascade": has_cascade,
                "nargs": lowered.nargs,
            }
            option_dict.update(extra_data)

            # Handle boolean optional action (--flag and --no-flag).
            if option_type == "boolean":
                option_dict["flags"].append(_arguments.flag_to_inverse(flag))

            options.append(option_dict)

    return options


def _is_path_argument(arg: _arguments.ArgumentDefinition) -> bool:
    """Check if an argument represents a file/directory path."""
    name_suggests_path = (
        arg.field.intern_name.endswith("_file")
        or arg.field.intern_name.endswith("_path")
        or arg.field.intern_name.endswith("_filename")
        or arg.field.intern_name.endswith("_dir")
        or arg.field.intern_name.endswith("_directory")
        or arg.field.intern_name.endswith("_folder")
    )

    type_suggests_path = "Path" in str(arg.field.type_stripped)

    if type_suggests_path:
        return True
    if "str" in str(arg.field.type_stripped) and name_suggests_path:
        return True

    return False


def _is_directory_argument(arg: _arguments.ArgumentDefinition) -> bool:
    """Check if an argument specifically represents a directory."""
    return (
        arg.field.intern_name.endswith("_dir")
        or arg.field.intern_name.endswith("_directory")
        or arg.field.intern_name.endswith("_folder")
    )


def _has_cascade_marker(arg: _arguments.ArgumentDefinition) -> bool:
    """Check if an argument has CascadeSubcommandArgs marker."""
    from ...conf import _markers

    return _markers.CascadeSubcommandArgs in arg.field.markers
