import sys
from dataclasses import dataclass
from typing import Annotated

import tyro
import tyro._fmtlib as fmt
from tyro._arguments import (
    BooleanOptionalAction,
    flag_to_inverse,
    generate_argument_helptext,
)
from tyro._parsers import ParserSpecification


def print_help(parser: ParserSpecification, prog: str = "script.py") -> None:
    usage_strings = []
    group_description: dict[str, str] = {}
    groups: dict[str, list[tuple[str | fmt._Text, fmt._Text]]] = {
        "positional arguments": [],
        "options": [("-h, --help", fmt.text["dim"]("show this help message and exit"))],
    }

    def recurse_args(parser: ParserSpecification, traversing_up: bool) -> None:
        # Note: multiple parsers can have the same extern_prefix. This might overwrite some groups.
        group_label = (parser.extern_prefix + " options").strip()
        groups.setdefault(group_label, [])
        if parser.extern_prefix != "":
            # Ignore root, since we'll show description above.
            group_description[group_label] = parser.description
        for arg in parser.args:
            # Update usage.
            if arg.field.is_positional():
                assert arg.lowered.metavar is not None
                invocation_short = fmt.text["bold"](arg.lowered.metavar)
                invocation_long_parts = [arg.lowered.metavar]
            else:
                name_or_flags = arg.lowered.name_or_flags
                if arg.lowered.action is BooleanOptionalAction:
                    name_or_flags = []
                    for name_or_flag in arg.lowered.name_or_flags:
                        name_or_flags.append(name_or_flag)
                        name_or_flags.append(flag_to_inverse(name_or_flag))
                    invocation_short = (
                        arg.lowered.name_or_flags[0]
                        + " | "
                        + flag_to_inverse(arg.lowered.name_or_flags[0])
                    )
                elif arg.lowered.metavar is not None:
                    invocation_short = fmt.text(
                        arg.lowered.name_or_flags[0],
                        " ",
                        fmt.text["bold"](arg.lowered.metavar),
                    )
                else:
                    invocation_short = arg.lowered.name_or_flags[0]

                if arg.lowered.required is not True:
                    invocation_short = fmt.text("[", invocation_short, "]")

                invocation_long_parts = []
                for i, name in enumerate(name_or_flags):
                    if i > 0:
                        invocation_long_parts.append(", ")

                    invocation_long_parts.append(name)
                    if arg.lowered.metavar is not None:
                        invocation_long_parts.append(" ")
                        invocation_long_parts.append(
                            fmt.text["bold"](arg.lowered.metavar)
                        )

            # Populate help window.
            usage_strings.append(invocation_short)
            helptext = generate_argument_helptext(arg, arg.lowered)
            groups[
                group_label if not arg.field.is_positional() else "positional arguments"
            ].append((fmt.text(*invocation_long_parts), helptext))
        if not traversing_up:
            for child in parser.child_from_prefix.values():
                recurse_args(child, traversing_up=False)
        if parser.consolidate_subcommand_args and parser.subparser_parent is not None:
            recurse_args(parser.subparser_parent, traversing_up=True)

    recurse_args(parser, traversing_up=False)

    # Compute maximum widths for formatting.
    max_invocation_width = 0
    widths = []
    for g in groups.values():
        for invocation, helptext in g:
            max_invocation_width = max(max_invocation_width, len(invocation))
            widths.append(len(invocation))
    if parser.subparsers is not None:
        for parser_name in parser.subparsers.parser_from_name.keys():
            # Add 4 for indentation.
            max_invocation_width = max(max_invocation_width, len(parser_name) + 4)
            widths.append(len(parser_name) + 4)

    # Limit maximum width to 24 characters.
    if max_invocation_width > 24:
        # Find the closest width just under the mean.
        mean_width = sum(widths) / len(widths)
        just_under_mean = 0
        for width in widths:
            if width < mean_width and width > just_under_mean:
                just_under_mean = width

        if just_under_mean > 24:
            max_invocation_width = 4
        else:
            max_invocation_width = just_under_mean

    # Put arguments in boxes.
    group_boxes = []
    for group_name, g in groups.items():
        if len(g) == 0:
            continue
        rows = []
        if group_description.get(group_name, "") != "":
            rows.append(group_description[group_name])
            rows.append(fmt.hr["dim"]())
        for invocation, helptext in g:
            if len(invocation) > max_invocation_width:
                # Invocation and helptext on separate lines.
                rows.append(invocation)
                rows.append(fmt.columns(("", max_invocation_width + 2), helptext))
            else:
                # Invocation and helptext on the same line.
                rows.append(
                    fmt.columns((invocation, max_invocation_width + 2), helptext)
                )
        group_boxes.append(
            fmt.box["dim"](
                fmt.text["dim"](group_name),
                fmt.rows(*rows),
            )
        )

    subcommand_metavar = ""
    if parser.subparsers is not None:
        default_name = parser.subparsers.default_name
        parser_from_name = parser.subparsers.parser_from_name

        rows = []
        subcommand_metavar = "{" + ",".join(parser_from_name.keys()) + "}"
        if default_name is not None:
            rows.append(fmt.text["bold"]("(default: ", default_name, ")"))
            rows.append(fmt.hr["dim"]())
            subcommand_metavar = f"[{subcommand_metavar}]"
        rows.append(subcommand_metavar)
        for name, subparser in parser_from_name.items():
            rows.append(
                fmt.columns(
                    ("", 4),
                    (name, max_invocation_width - 2),
                    fmt.text["dim"](subparser.description or ""),
                )
            )

        group_boxes.append(
            fmt.box["dim"](
                fmt.text["dim"]("subcommands"),
                fmt.rows(*rows),
            )
        )

    usage_parts = [fmt.text["bold"]("usage:"), prog, "[-h]"]
    usage_args = fmt.text(*usage_strings, delimeter=" ")
    if len(usage_args) > 0:
        # TODO: needs subcommand name.
        usage_parts.append(usage_args if len(usage_args) < 80 else "[OPTIONS]")
    if subcommand_metavar != "":
        usage_parts.append(subcommand_metavar)

    helptext = fmt.rows(*group_boxes)
    print(*fmt.text(*usage_parts, delimeter=" ").render(), sep="\n")
    if parser.description == "":
        print()
    else:
        print()
        print(parser.description)
        print()
    print(*helptext.render(min(160, helptext.max_width())), sep="\n")
