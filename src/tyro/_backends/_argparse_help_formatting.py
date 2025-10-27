"""Help formatting utils used for argparse backend."""

from __future__ import annotations

import dataclasses
import difflib
import shlex
import shutil
import sys
from typing import TYPE_CHECKING, NoReturn

from tyro.conf._markers import CascadeSubcommandArgs
from tyro.conf._mutex_group import _MutexGroupConfig

from .. import _fmtlib as fmt
from .. import _settings, conf

if TYPE_CHECKING:
    from .._arguments import ArgumentDefinition
    from .._parsers import ParserSpecification, SubparsersSpecification


def format_help(
    prog: str,
    parser_specs: list[ParserSpecification],
    subparser_frontier: dict[str, SubparsersSpecification],
) -> list[str]:
    usage_strings = []
    group_description: dict[str, str] = {}
    groups: dict[str | _MutexGroupConfig, list[tuple[str | fmt._Text, fmt._Text]]] = {
        "positional arguments": [],
        "options": [("-h, --help", fmt.text["dim"]("show this help message and exit"))],
    }

    # Iterate over all provided parser specs and collect their arguments.
    from .._arguments import generate_argument_helptext

    def add_args_recursive(parser: ParserSpecification) -> None:
        """Recursively add arguments from a parser and its children."""
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

            # How should this argument be grouped?
            arg_group: str | _MutexGroupConfig
            if arg.field.mutex_group is not None:
                arg_group = arg.field.mutex_group
            elif arg.is_positional():
                arg_group = "positional arguments"
            else:
                arg_group = group_label

            # Add argument to group.
            if arg_group not in groups:
                groups[arg_group] = []
            groups[arg_group].append((invocation_long, helptext))

        # Recurse into child parsers (for nested dataclass fields).
        for child in parser.child_from_prefix.values():
            add_args_recursive(child)

    for parser_spec in parser_specs:
        add_args_recursive(parser_spec)

    # Compute maximum widths for formatting.
    max_invocation_width = 0
    widths = []
    for g in groups.values():
        for invocation, helptext in g:
            max_invocation_width = max(max_invocation_width, len(invocation))
            widths.append(len(invocation))

    # Account for subparser names in the frontier.
    for subparser_spec in subparser_frontier.values():
        for parser_name in subparser_spec.parser_from_name.keys():
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
    for group_key, g in groups.items():
        if len(g) == 0:
            continue
        rows: list[str | fmt.Element] = []

        if isinstance(group_key, _MutexGroupConfig):
            rows.append(
                fmt.text(
                    "Exactly one argument must be passed in. ",
                    fmt.text["bright_red"]("(required)"),
                )
                if group_key.required
                else "At most one argument can be overridden.",
            )
            rows.append(fmt.hr[_settings.ACCENT_COLOR, "dim"]())
        elif group_description.get(group_key, "") != "":
            rows.append(group_description[group_key])
            rows.append(fmt.hr[_settings.ACCENT_COLOR, "dim"]())

        for invocation, helptext in g:
            if len(invocation) > max_invocation_width:
                # Invocation and helptext on separate lines.
                rows.append(invocation)
                rows.append(fmt.cols(("", max_invocation_width + 2), helptext))
            else:
                # Invocation and helptext on the same line.
                rows.append(fmt.cols((invocation, max_invocation_width + 2), helptext))
        group_boxes.append(
            fmt.box[_settings.ACCENT_COLOR, "dim"](
                fmt.text[_settings.ACCENT_COLOR, "dim"](
                    (
                        group_key.title
                        if group_key.title is not None
                        else "mutually exclusive"
                    )
                    if isinstance(group_key, _MutexGroupConfig)
                    else group_key
                ),
                fmt.rows(*rows),
            )
        )
        group_heights.append(len(rows) + 2)

    # Populate subcommand info from frontier.
    # Create a separate box for each subparser group in the frontier.
    subcommand_metavars: list[str] = []
    for intern_prefix, subparser_spec in subparser_frontier.items():
        default_name = subparser_spec.default_name
        parser_from_name = subparser_spec.parser_from_name

        rows = []
        metavar = "{" + ",".join(parser_from_name.keys()) + "}"

        if subparser_spec.description is not None:
            rows.append(subparser_spec.description)
            rows.append(fmt.hr[_settings.ACCENT_COLOR, "dim"]())

        if default_name is not None:
            rows.append(
                fmt.text(
                    "Options ",
                    fmt.text[
                        "bold",
                        _settings.ACCENT_COLOR
                        if _settings.ACCENT_COLOR != "white"
                        else "cyan",
                    ]("(default: ", default_name, ")"),
                )
            )
        elif subparser_spec.required:
            rows.append(
                fmt.text("Options ", fmt.text["bold", "bright_red"]("(required)"))
            )

        for name, child_parser_spec in parser_from_name.items():
            if len(name) <= max_invocation_width - 2:
                rows.append(
                    fmt.cols(
                        ("", 4),
                        (name, max_invocation_width - 2),
                        fmt.text["dim"](child_parser_spec.description.strip() or ""),
                    )
                )
            else:
                rows.append(
                    fmt.cols(
                        ("", 4),
                        name.strip(),
                    )
                )
                desc = child_parser_spec.description.strip()
                if len(desc):
                    rows.append(fmt.text["dim"](desc))

        # Use the extern_prefix as the title if available, otherwise "subcommands".
        title = "subcommands"
        if subparser_spec.extern_prefix != "":
            title = subparser_spec.extern_prefix + " subcommands"

        # For usage line: use full {a,b,c} metavar when there's only one subparser
        # group in the frontier. Otherwise use shortened CAPS form for cleaner usage.
        if len(subparser_frontier) == 1:
            # Single subparser group: use full metavar like {a,checkout-completion}.
            usage_metavar = metavar
        else:
            # Multiple subparser groups: use shortened form like A, B, etc.
            usage_metavar = title.replace(" subcommands", "").replace(" ", "-").upper()
        if default_name is not None:
            usage_metavar = f"[{usage_metavar}]"
        subcommand_metavars.append(usage_metavar)

        group_boxes.append(
            fmt.box[_settings.ACCENT_COLOR, "dim"](
                fmt.text[_settings.ACCENT_COLOR, "dim"](title),
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

    helptext_cols = fmt.cols(*(fmt.rows(*col_boxes) for col_boxes in cols))

    # Format usage.
    usage_parts: list[fmt._Text | str] = [fmt.text["bold"]("usage:"), prog, "[-h]"]
    usage_args = fmt.text(*usage_strings, delimeter=" ")
    if len(usage_args) > 0:
        # TODO: needs subcommand name.
        if len(usage_args) < 80:
            usage_parts.append(usage_args)
        else:
            prog_parts = shlex.split(prog)
            # Use the first parser spec to determine if this is root.
            is_root = len(parser_specs) > 0 and parser_specs[0].intern_prefix == ""
            usage_parts.append(
                "[OPTIONS]" if is_root else f"[{prog_parts[-1].upper()} OPTIONS]"
            )
    # Add all subcommand metavars from the frontier.
    for metavar in subcommand_metavars:
        usage_parts.append(metavar)

    out = []
    out.extend(fmt.text(*usage_parts, delimeter=" ").render())
    # Use the first (root) parser spec for the main description.
    root_description = parser_specs[0].description if len(parser_specs) > 0 else ""
    if root_description == "":
        out.append("")
    else:
        out.append("")
        out.append(root_description)
        out.append("")
    out.extend(
        helptext_cols.render(
            min(shutil.get_terminal_size().columns, helptext_cols.max_width())
        )
    )
    return out


def recursive_arg_search(
    args: list[str],
    parser_spec: ParserSpecification,
    prog: str,
    unrecognized_arguments: set[str],
) -> tuple[list[_ArgumentInfo], bool, bool]:
    """Recursively search for arguments in a ParserSpecification. Used for error message
    printing.

    Returns a list of arguments, whether the parser has subcommands or not, and -- if
    `unrecognized_arguments` is passed in --- whether an unrecognized argument exists
    under a different subparser.

    Args:
        args: Arguments being parsed. Used for heuristics on subcommands.
        parser_spec: Argument parser specification.
        subcommands: Prog corresponding to parser_spec.
        unrecognized_arguments: Used for same_exists return value.
    """
    # Argument name => subcommands it came from.
    arguments: list[_ArgumentInfo] = []
    has_subcommands = False
    same_exists = False

    def _recursive_arg_search(
        parser_spec: ParserSpecification,
        prog: str,
        subcommand_match_score: float,
    ) -> None:
        """Find all possible arguments that could have been passed in."""

        # When tyro.conf.CascadeSubcommandArgs is turned on, arguments will
        # only appear in the help message for "leaf" subparsers.
        help_flag = (
            " (other subcommands) --help"
            if CascadeSubcommandArgs in parser_spec.markers
            and len(parser_spec.subparsers_from_intern_prefix) > 0
            else " --help"
        )
        for arg in parser_spec.args:
            if arg.is_positional() or arg.lowered.is_fixed():
                # Skip positional arguments.
                continue

            # Skip suppressed arguments.
            if conf.Suppress in arg.field.markers or (
                conf.SuppressFixed in arg.field.markers
                and conf.Fixed in arg.field.markers
            ):
                continue

            option_strings = arg.lowered.name_or_flags

            # Handle actions, eg BooleanOptionalAction will map ("--flag",) to
            # ("--flag", "--no-flag").
            if arg.lowered.action == "boolean_optional_action":
                from .._arguments import flag_to_inverse

                option_strings = option_strings + tuple(
                    flag_to_inverse(option) for option in option_strings
                )

            arguments.append(
                _ArgumentInfo(
                    # Currently doesn't handle actions well, eg boolean optional
                    # arguments.
                    arg,
                    option_strings=option_strings,
                    metavar=arg.lowered.metavar,
                    usage_hint=prog + help_flag,
                    help=arg.lowered.help,
                    subcommand_match_score=subcommand_match_score,
                )
            )

            # An unrecognized argument.
            nonlocal same_exists
            if not same_exists and any(
                map(lambda x: x in unrecognized_arguments, arg.lowered.name_or_flags)
            ):
                same_exists = True

        # Check subparsers from the parser spec's frontier.
        if len(parser_spec.subparsers_from_intern_prefix) > 0:
            nonlocal has_subcommands
            has_subcommands = True
            for subparser_spec in parser_spec.subparsers_from_intern_prefix.values():
                for (
                    subparser_name,
                    child_parser_spec,
                ) in subparser_spec.parser_from_name.items():
                    _recursive_arg_search(
                        child_parser_spec.evaluate(),
                        prog + " " + subparser_name,
                        # Leaky (!!) heuristic for if this subcommand is matched or not.
                        subcommand_match_score=subcommand_match_score
                        + (1 if subparser_name in args else -0.001),
                    )

        for child in parser_spec.child_from_prefix.values():
            _recursive_arg_search(child, prog, subcommand_match_score)

    _recursive_arg_search(parser_spec, prog, 0)

    return arguments, has_subcommands, same_exists


def unrecognized_args_error(
    prog: str,
    unrecognized_args_and_progs: list[tuple[str, str]],
    args: list[str],
    parser_spec: ParserSpecification,
    console_outputs: bool,
    add_help: bool,
) -> NoReturn:
    message_fmt = fmt.text(
        f"Unrecognized options: {' '.join([arg for arg, _ in unrecognized_args_and_progs])}"
    )
    extra_info: list[fmt.Element | str] = []

    unrecognized_arguments = set(
        arg
        for arg, _ in unrecognized_args_and_progs
        # If we pass in `--spell-chekc on`, we only want `spell-chekc` and not
        # `on`.
        if arg.startswith("--")
    )
    arguments, has_subcommands, same_exists = recursive_arg_search(
        args=args,
        parser_spec=parser_spec,
        prog=prog.partition(" ")[0],
        unrecognized_arguments=unrecognized_arguments,
    )

    if has_subcommands and same_exists:
        message_fmt = fmt.text("Unrecognized or misplaced options:\n\n")
        for arg, arg_prog in unrecognized_args_and_progs:
            message_fmt = fmt.text(
                message_fmt,
                f"  {arg} (applied to ",
                fmt.text["green"](arg_prog),
                ")\n",
            )
        message_fmt = fmt.text(
            message_fmt,
            "\nArguments are applied to the directly preceding subcommand, so ordering can matter.",
        )

    # Show similar arguments for keyword options.
    for unrecognized_argument in unrecognized_arguments:
        # Sort arguments by similarity.
        scored_arguments: list[tuple[_ArgumentInfo, float]] = []
        for arg_info in arguments:
            # Compute a score for each argument.
            assert unrecognized_argument.startswith("--")

            def get_score(option_string: str) -> float:
                if option_string.endswith(
                    unrecognized_argument[2:]
                ) or option_string.startswith(unrecognized_argument[2:]):
                    return 0.9
                elif len(unrecognized_argument) >= 4 and all(
                    map(
                        lambda part: part in option_string,
                        unrecognized_argument[2:].split("."),
                    )
                ):
                    return 0.9
                else:
                    return difflib.SequenceMatcher(
                        a=unrecognized_argument, b=option_string
                    ).ratio()

            scored_arguments.append(
                (arg_info, max(map(get_score, arg_info.option_strings)))
            )

        # Add information about similar arguments.
        prev_arg_option_strings: tuple[str, ...] | None = None
        show_arguments: list[_ArgumentInfo] = []
        unique_counter = 0
        for arg_info, score in (
            # Sort scores greatest to least.
            sorted(
                scored_arguments,
                key=lambda arg_score: (
                    # Highest scores first.
                    -arg_score[1],
                    # Prefer arguments available in the currently specified
                    # subcommands.
                    -arg_score[0].subcommand_match_score,
                    # Cluster by flag name, metavar, usage hint, help message.
                    arg_score[0].option_strings[0],
                    arg_score[0].metavar,
                    arg_score[0].usage_hint,
                    arg_score[0].help,
                ),
            )
        ):
            if score < 0.8:
                break
            if (
                score < 0.9
                and unique_counter >= 3
                and prev_arg_option_strings != arg_info.option_strings
            ):
                break
            unique_counter += prev_arg_option_strings != arg_info.option_strings

            show_arguments.append(arg_info)
            prev_arg_option_strings = arg_info.option_strings

        prev_arg_info: _ArgumentInfo | None = None
        same_counter = 0
        dots_printed = False
        if len(show_arguments) > 0:
            # Add a header before the first similar argument.
            extra_info.append(fmt.hr["red"]())
            extra_info.append(
                "Perhaps you meant:"
                if len(unrecognized_arguments) == 1
                else f"Arguments similar to {unrecognized_argument}:"
            )

        unique_counter = 0
        for arg_info in show_arguments:
            same_counter += 1
            if (
                prev_arg_info is None
                or arg_info.option_strings != prev_arg_info.option_strings
            ):
                same_counter = 0
                if unique_counter >= 10:
                    break
                unique_counter += 1

            # For arguments with the same name, only show a limited number of
            # subcommands / help messages.
            if (
                len(show_arguments) >= 8
                and same_counter >= 4
                and prev_arg_info is not None
                and arg_info.option_strings == prev_arg_info.option_strings
            ):
                if not dots_printed:
                    extra_info.append(
                        fmt.cols(
                            ("", 4),
                            "[...]",
                        )
                    )
                dots_printed = True
                continue

            if not (
                has_subcommands
                and prev_arg_info is not None
                and arg_info.option_strings == prev_arg_info.option_strings
                and arg_info.metavar == prev_arg_info.metavar
            ):
                extra_info.append(
                    fmt.cols(
                        ("", 4),
                        (
                            ", ".join(arg_info.option_strings)
                            if arg_info.metavar is None
                            else ", ".join(arg_info.option_strings)
                            + " "
                            + arg_info.metavar
                        ),
                    )
                )

            from .._arguments import generate_argument_helptext

            helptext = generate_argument_helptext(arg_info.arg, arg_info.arg.lowered)
            if helptext is not None and (
                # Only print help messages if it's not the same as the previous
                # one.
                prev_arg_info is None
                or arg_info.help != prev_arg_info.help
                or arg_info.option_strings != prev_arg_info.option_strings
                or arg_info.metavar != prev_arg_info.metavar
            ):
                extra_info.append(fmt.cols(("", 8), helptext))

            # Show the subcommand that this argument is available in.
            if has_subcommands:
                extra_info.append(
                    fmt.cols(
                        ("", 8),
                        fmt.text("in ", fmt.text["green"](arg_info.usage_hint)),
                    )
                )

            prev_arg_info = arg_info

    error_and_exit(
        "Unrecognized options",
        message_fmt,
        *extra_info,
        prog=prog,
        console_outputs=console_outputs,
        add_help=add_help,
    )


def required_args_error(
    prog: str,
    required_args: list[str],
    args: list[str],
    parser_spec: ParserSpecification,
    console_outputs: bool,
    add_help: bool,
) -> NoReturn:
    extra_info: list[fmt.Element | str] = []

    info_from_required_arg: dict[str, _ArgumentInfo | None] = {
        arg: None for arg in required_args
    }
    arguments, has_subcommands, same_exists = recursive_arg_search(
        args=args,
        parser_spec=parser_spec,
        prog=prog,
        unrecognized_arguments=set(),
    )
    del same_exists

    for arg_info in arguments:
        # Iterate over each option string separately. This can help us support
        # aliases in the future.
        for option_string in arg_info.option_strings:
            # If the option string was found...
            if option_string in info_from_required_arg and (
                # And it's the first time it was found...
                info_from_required_arg[option_string] is None
                # Or we found a better one...
                or arg_info.subcommand_match_score
                > info_from_required_arg[option_string].subcommand_match_score  # type: ignore
            ):
                # Record the argument info.
                info_from_required_arg[option_string] = arg_info

    # Try to print help text for required arguments.
    first = True
    for maybe_arg in info_from_required_arg.values():
        if maybe_arg is None:
            # No argument info found. This will currently happen for
            # subcommands.
            continue

        if first:
            extra_info.extend(
                [
                    fmt.hr["red"](),
                    "Argument helptext:",
                ]
            )
            first = False

        extra_info.append(
            fmt.cols(
                ("", 4),
                fmt.text["bold"](maybe_arg.arg.get_invocation_text()[1]),
            )
        )
        from .._arguments import generate_argument_helptext

        helptext = generate_argument_helptext(maybe_arg.arg, maybe_arg.arg.lowered)
        if len(helptext) > 0:
            extra_info.append(fmt.cols(("", 8), helptext))
        if has_subcommands:
            # We are explicit about where the argument helptext is being
            # extracted from because the `subcommand_match_score` heuristic
            # above is flawed.
            #
            # The stars really need to be aligned for it to fail, but this makes
            # sure that if it does fail that it's obvious to the user.
            extra_info.append(
                fmt.cols(
                    ("", 12),
                    fmt.text("in ", fmt.text["green"](maybe_arg.usage_hint)),
                )
            )
    error_and_exit(
        "Required options",
        fmt.text(
            "Required options were not provided: ",
            fmt.text["red", "bold"](", ".join(required_args)),
        ),
        *extra_info,
        prog=prog,
        console_outputs=console_outputs,
        add_help=add_help,
    )


def error_and_exit(
    title: str,
    *contents: fmt.Element | str,
    prog: str,
    console_outputs: bool,
    add_help: bool,
) -> NoReturn:
    if console_outputs:
        print(
            fmt.box["red"](
                fmt.text["red", "bold"](title),
                fmt.rows(
                    *contents,
                    *[
                        fmt.hr["red"](),
                        fmt.text(
                            "For full helptext, run ",
                            fmt.text["bold"](prog + " --help"),
                        ),
                    ]
                    if add_help
                    else [],
                ),
            ),
            file=sys.stderr,
            flush=True,
        )
    sys.exit(2)


@dataclasses.dataclass(frozen=True)
class _ArgumentInfo:
    arg: ArgumentDefinition
    option_strings: tuple[str, ...]
    metavar: str | None
    usage_hint: str
    help: str | None
    subcommand_match_score: float
    """Priority value used when an argument is in the current subcommand tree."""
