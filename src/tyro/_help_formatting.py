import shlex
import shutil

from . import _argparse_formatter as _af
from . import _fmtlib as fmt
from ._arguments import generate_argument_helptext
from ._parsers import ParserSpecification


def format_help(parser: ParserSpecification, prog: str = "script.py") -> list[str]:
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
            if arg.is_suppressed():
                continue

            # Populate help window.
            invocation_short, invocation_long = arg.get_invocation_text()
            usage_strings.append(invocation_short)
            helptext = generate_argument_helptext(arg, arg.lowered)
            groups[
                group_label if not arg.field.is_positional() else "positional arguments"
            ].append((invocation_long, helptext))
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
    group_boxes: list[fmt._Box] = []
    group_heights: list[int] = []
    for group_name, g in groups.items():
        if len(g) == 0:
            continue
        rows = []
        if group_description.get(group_name, "") != "":
            rows.append(group_description[group_name])
            rows.append(fmt.hr[_af.ACCENT_COLOR, "dim"]())
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
            fmt.box[_af.ACCENT_COLOR, "dim"](
                fmt.text[_af.ACCENT_COLOR, "dim"](group_name),
                fmt.rows(*rows),
            )
        )
        group_heights.append(len(rows) + 2)

    # Populate info.
    subcommand_metavar = ""
    if parser.subparsers is not None:
        default_name = parser.subparsers.default_name
        parser_from_name = parser.subparsers.parser_from_name

        rows = []
        subcommand_metavar = "{" + ",".join(parser_from_name.keys()) + "}"
        needs_hr = False
        if parser.subparsers.description is not None:
            rows.append(parser.subparsers.description)
            needs_hr = True
        if default_name is not None:
            rows.append(fmt.text["bold"]("(default: ", default_name, ")"))
            subcommand_metavar = f"[{subcommand_metavar}]"
            needs_hr = True

        if needs_hr:
            rows.append(fmt.hr[_af.ACCENT_COLOR, "dim"]())
        rows.append(subcommand_metavar)
        for name, subparser in parser_from_name.items():
            if len(name) <= max_invocation_width - 2:
                rows.append(
                    fmt.columns(
                        ("", 4),
                        (name, max_invocation_width - 2),
                        fmt.text["dim"](subparser.description.strip() or ""),
                    )
                )
            else:
                rows.append(
                    fmt.columns(
                        ("", 4),
                        name.strip(),
                    )
                )
                desc = subparser.description.strip()
                if len(desc):
                    rows.append(fmt.text["dim"](desc))

        group_boxes.append(
            fmt.box[_af.ACCENT_COLOR, "dim"](
                fmt.text[_af.ACCENT_COLOR, "dim"]("subcommands"),
                fmt.rows(*rows),
            )
        )
        group_heights.append(len(rows) + 2)

    # Arrange group boxes into columns.
    cols: tuple[list[fmt._Box], ...] = ()
    height_breakpoint = 60
    screen_width = shutil.get_terminal_size().columns
    max_column_count = max(
        1,
        min(
            sum(group_heights) // height_breakpoint + 1,
            screen_width // 65,
            len(group_boxes),
        ),
    )
    for num_columns in reversed(range(1, max_column_count + 1)):
        # Greedily fill shortest columns with boxes. This is somewhat naive; it
        # doesn't consider possible wrapping in helptext.
        col_heights = [0] * num_columns
        cols = tuple([] for _ in range(num_columns))
        for box, height in zip(group_boxes, group_heights):
            col_index = col_heights.index(min(col_heights))
            cols[col_index].append(box)
            col_heights[col_index] += height

        # Done if we're down to one column or all columns are
        # within 60% of the maximum height.
        #
        # We use these ratios to prevent large hanging columns: https://github.com/brentyi/tyro/issues/222
        max_col_height = max(*col_heights, 1)
        if all([col_height >= max_col_height * 0.6 for col_height in col_heights]):
            break

    helptext = fmt.columns(*(fmt.rows(*col_boxes) for col_boxes in cols))

    # Format usage.
    usage_parts = [fmt.text["bold"]("usage:"), prog, "[-h]"]
    usage_args = fmt.text(*usage_strings, delimeter=" ")
    if len(usage_args) > 0:
        # TODO: needs subcommand name.
        if len(usage_args) < 80:
            usage_parts.append(usage_args)
        else:
            prog_parts = shlex.split(prog)
            usage_parts.append(
                "[OPTIONS]"
                if parser.intern_prefix == ""  # Root parser has no prefix.
                else f"[{prog_parts[-1].upper()} OPTIONS]"
            )
    if subcommand_metavar != "":
        usage_parts.append(subcommand_metavar)

    out = []
    out.extend(fmt.text(*usage_parts, delimeter=" ").render())
    if parser.description == "":
        out.append("")
    else:
        out.append("")
        out.append(parser.description)
        out.append("")
    out.extend(
        helptext.render(min(shutil.get_terminal_size().columns, helptext.max_width()))
    )
    return out + [""]
