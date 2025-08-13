"""Utilities and functions for helptext formatting. We replace argparse's simple help
messages with ones that:
    - Are more nicely formatted!
    - Support multiple columns when many fields are defined.
    - Can be themed with an accent color.

This is largely built by fussing around in argparse implementation details. It's
chaotic as a result; for stability we mirror argparse at _argparse.py.
"""

from __future__ import annotations

import argparse as argparse_sys
import dataclasses
import difflib
import sys
from gettext import gettext as _
from typing import Dict, List, Literal, NoReturn, Optional, Set, Tuple

from typing_extensions import override

from . import _argparse as argparse
from . import _fmtlib as fmt
from . import conf
from ._arguments import ArgumentDefinition, generate_argument_helptext
from ._parsers import ParserSpecification

# TODO: revisit global.
ACCENT_COLOR: fmt.AnsiAttribute = "white"


def set_accent_color(
    accent_color: Literal[
        "black",
        "red",
        "green",
        "yellow",
        "blue",
        "magenta",
        "cyan",
        "white",
        "bright_black",
        "bright_red",
        "bright_green",
        "bright_yellow",
        "bright_blue",
        "bright_magenta",
        "bright_cyan",
        "bright_white",
    ]
    | None,
) -> None:
    """Set an accent color to use in help messages. Experimental."""
    global ACCENT_COLOR
    ACCENT_COLOR = accent_color if accent_color is not None else "white"


def recursive_arg_search(
    args: List[str],
    parser_spec: ParserSpecification,
    prog: str,
    unrecognized_arguments: Set[str],
) -> Tuple[List[_ArgumentInfo], bool, bool]:
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
    arguments: List[_ArgumentInfo] = []
    has_subcommands = False
    same_exists = False

    def _recursive_arg_search(
        parser_spec: ParserSpecification,
        prog: str,
        subcommand_match_score: float,
    ) -> None:
        """Find all possible arguments that could have been passed in."""

        # When tyro.conf.ConsolidateSubcommandArgs is turned on, arguments will
        # only appear in the help message for "leaf" subparsers.
        help_flag = (
            " (other subcommands) --help"
            if parser_spec.consolidate_subcommand_args
            and parser_spec.subparsers is not None
            else " --help"
        )
        for arg in parser_spec.args:
            if arg.field.is_positional() or arg.lowered.is_fixed():
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
            if (
                arg.lowered.action is not None
                # Actions are sometimes strings in Python 3.7, eg "append".
                # We'll ignore these, but this kind of thing is a good reason
                # for just forking argparse.
                and callable(arg.lowered.action)
            ):
                option_strings = arg.lowered.action(
                    option_strings,
                    dest="",  # dest should not matter.
                ).option_strings  # type: ignore

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

        if parser_spec.subparsers is not None:
            nonlocal has_subcommands
            has_subcommands = True
            for (
                subparser_name,
                subparser,
            ) in parser_spec.subparsers.parser_from_name.items():
                _recursive_arg_search(
                    subparser,
                    prog + " " + subparser_name,
                    # Leaky (!!) heuristic for if this subcommand is matched or not.
                    subcommand_match_score=subcommand_match_score
                    + (1 if subparser_name in args else -0.001),
                )

        for child in parser_spec.child_from_prefix.values():
            _recursive_arg_search(child, prog, subcommand_match_score)

    _recursive_arg_search(parser_spec, prog, 0)

    return arguments, has_subcommands, same_exists


@dataclasses.dataclass(frozen=True)
class _ArgumentInfo:
    arg: ArgumentDefinition
    option_strings: Tuple[str, ...]
    metavar: Optional[str]
    usage_hint: str
    help: Optional[str]
    subcommand_match_score: float
    """Priority value used when an argument is in the current subcommand tree."""


# By default, unrecognized arguments won't raise an error in the case of:
#
#     # We've misspelled `binary`!
#     python 03_multiple_subcommands.py dataset:mnist --dataset.binayr True
#
# When there's a subcommand that follows dataset:mnist. Instead,
# --dataset.binayr is consumed and we get an error that `True` is not a valid
# subcommand. This can be really confusing when we have a lot of keyword
# arguments.
#
# Our current solution is to manually track unrecognized arguments in _parse_known_args,
# and in error() override other errors when unrecognized arguments are present.
global_unrecognized_arg_and_prog: List[Tuple[str, str]] = []


# We inherit from both our local mirror of argparse and the upstream one.
# Including the latter is purely for `isinstance()`-style checks.
class TyroArgumentParser(argparse.ArgumentParser, argparse_sys.ArgumentParser):  # type: ignore
    _parser_specification: ParserSpecification
    _parsing_known_args: bool
    _console_outputs: bool
    _args: List[str]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    @override
    def _check_value(self, action, value):
        """We override _check_value to ignore sentinel values defined by tyro.

        This solves a choices error raised by argparse in a very specific edge case:
        literals in containers as positional arguments.
        """
        from ._fields import MISSING_AND_MISSING_NONPROP

        if value in MISSING_AND_MISSING_NONPROP:
            return
        return super()._check_value(action, value)

    @override
    def _print_message(self, message, file=None):
        if message and self._console_outputs:
            file = file or sys.stderr
            try:
                file.write(message)
            except (AttributeError, OSError):  # pragma: no cover
                pass

    @override
    def format_help(self) -> str:
        from ._custom_backend import format_help

        return "\n".join(format_help(self._parser_specification, self.prog))

    # @override
    def _parse_known_args(  # type: ignore
        self, arg_strings, namespace
    ):  # pragma: no cover
        """We override _parse_known_args() to improve error messages in the presence of
        subcommands. Difference is marked with <new>...</new> below."""

        # <new>
        # Reset the unused argument list in the root parser.
        # Subparsers will have spaces in self.prog.
        if " " not in self.prog:
            global global_unrecognized_arg_and_prog
            global_unrecognized_arg_and_prog = []
        # </new>

        # replace arg strings that are file references
        if self.fromfile_prefix_chars is not None:
            arg_strings = self._read_args_from_files(arg_strings)

        # map all mutually exclusive arguments to the other arguments
        # they can't occur with
        action_conflicts = {}
        for mutex_group in self._mutually_exclusive_groups:
            group_actions = mutex_group._group_actions
            for i, mutex_action in enumerate(mutex_group._group_actions):
                conflicts = action_conflicts.setdefault(mutex_action, [])
                conflicts.extend(group_actions[:i])
                conflicts.extend(group_actions[i + 1 :])

        # find all option indices, and determine the arg_string_pattern
        # which has an 'O' if there is an option at an index,
        # an 'A' if there is an argument, or a '-' if there is a '--'
        option_string_indices = {}
        arg_string_pattern_parts = []
        arg_strings_iter = iter(arg_strings)
        for i, arg_string in enumerate(arg_strings_iter):
            # all args after -- are non-options
            if arg_string == "--":
                arg_string_pattern_parts.append("-")
                for arg_string in arg_strings_iter:
                    arg_string_pattern_parts.append("A")

            # otherwise, add the arg to the arg strings
            # and note the index if it was an option
            else:
                option_tuple = self._parse_optional(arg_string)
                if option_tuple is None:
                    pattern = "A"
                else:
                    option_string_indices[i] = option_tuple
                    pattern = "O"
                arg_string_pattern_parts.append(pattern)

        # join the pieces together to form the pattern
        arg_strings_pattern = "".join(arg_string_pattern_parts)

        # converts arg strings to the appropriate and then takes the action
        seen_actions = set()
        seen_non_default_actions = set()

        def take_action(action, argument_strings, option_string=None):
            seen_actions.add(action)
            argument_values = self._get_values(action, argument_strings)

            # error if this argument is not allowed with other previously
            # seen arguments, assuming that actions that use the default
            # value don't really count as "present"
            if argument_values is not action.default:
                seen_non_default_actions.add(action)
                for conflict_action in action_conflicts.get(action, []):
                    if conflict_action in seen_non_default_actions:
                        msg = _("not allowed with argument %s")
                        action_name = argparse._get_action_name(conflict_action)
                        raise argparse.ArgumentError(action, msg % action_name)

            # take the action if we didn't receive a SUPPRESS value
            # (e.g. from a default)
            if argument_values is not argparse.SUPPRESS:
                action(self, namespace, argument_values, option_string)

        # function to convert arg_strings into an optional action
        def consume_optional(start_index):
            # get the optional identified at this index
            option_tuple = option_string_indices[start_index]
            action, option_string, sep, explicit_arg = option_tuple

            # identify additional optionals in the same arg string
            # (e.g. -xyz is the same as -x -y -z if no args are required)
            match_argument = self._match_argument
            action_tuples = []
            while True:
                # if we found no optional action, skip it
                if action is None:
                    # <new>
                    # Manually track unused arguments to assist with error messages
                    # later.
                    if not self._parsing_known_args:
                        global_unrecognized_arg_and_prog.append(
                            (option_string, self.prog)
                        )
                    # </new>
                    extras.append(arg_strings[start_index])
                    return start_index + 1

                # if there is an explicit argument, try to match the
                # optional's string arguments to only this
                if explicit_arg is not None:
                    arg_count = match_argument(action, "A")

                    # if the action is a single-dash option and takes no
                    # arguments, try to parse more single-dash options out
                    # of the tail of the option string
                    chars = self.prefix_chars
                    if (
                        arg_count == 0
                        and option_string[1] not in chars
                        and explicit_arg != ""
                    ):
                        if sep or explicit_arg[0] in chars:
                            msg = _("ignored explicit argument %r")
                            raise argparse.ArgumentError(action, msg % explicit_arg)
                        action_tuples.append((action, [], option_string))
                        char = option_string[0]
                        option_string = char + explicit_arg[0]
                        optionals_map = self._option_string_actions
                        if option_string in optionals_map:
                            action = optionals_map[option_string]
                            explicit_arg = explicit_arg[1:]
                            if not explicit_arg:
                                sep = explicit_arg = None
                            elif explicit_arg[0] == "=":
                                sep = "="
                                explicit_arg = explicit_arg[1:]
                            else:
                                sep = ""
                        else:
                            extras.append(char + explicit_arg)
                            stop = start_index + 1
                            break
                    # if the action expect exactly one argument, we've
                    # successfully matched the option; exit the loop
                    elif arg_count == 1:
                        stop = start_index + 1
                        args = [explicit_arg]
                        action_tuples.append((action, args, option_string))
                        break

                    # error if a double-dash option did not use the
                    # explicit argument
                    else:
                        msg = _("ignored explicit argument %r")
                        raise argparse.ArgumentError(action, msg % explicit_arg)

                # if there is no explicit argument, try to match the
                # optional's string arguments with the following strings
                # if successful, exit the loop
                else:
                    start = start_index + 1
                    selected_patterns = arg_strings_pattern[start:]
                    arg_count = match_argument(action, selected_patterns)
                    stop = start + arg_count
                    args = arg_strings[start:stop]
                    action_tuples.append((action, args, option_string))
                    break

            # add the Optional to the list and return the index at which
            # the Optional's string args stopped
            assert action_tuples
            for action, args, option_string in action_tuples:
                take_action(action, args, option_string)
            return stop

        # the list of Positionals left to be parsed; this is modified
        # by consume_positionals()
        positionals = self._get_positional_actions()

        # function to convert arg_strings into positional actions
        def consume_positionals(start_index):
            # match as many Positionals as possible
            match_partial = self._match_arguments_partial
            selected_pattern = arg_strings_pattern[start_index:]
            arg_counts = match_partial(positionals, selected_pattern)

            # slice off the appropriate arg strings for each Positional
            # and add the Positional and its args to the list
            for action, arg_count in zip(positionals, arg_counts):
                args = arg_strings[start_index : start_index + arg_count]
                start_index += arg_count
                take_action(action, args)

            # slice off the Positionals that we just parsed and return the
            # index at which the Positionals' string args stopped
            positionals[:] = positionals[len(arg_counts) :]
            return start_index

        # consume Positionals and Optionals alternately, until we have
        # passed the last option string
        extras = []
        start_index = 0
        if option_string_indices:
            max_option_string_index = max(option_string_indices)
        else:
            max_option_string_index = -1
        while start_index <= max_option_string_index:
            # consume any Positionals preceding the next option
            next_option_string_index = min(
                [index for index in option_string_indices if index >= start_index]
            )
            if start_index != next_option_string_index:
                positionals_end_index = consume_positionals(start_index)

                # only try to parse the next optional if we didn't consume
                # the option string during the positionals parsing
                if positionals_end_index > start_index:
                    start_index = positionals_end_index
                    continue
                else:
                    start_index = positionals_end_index

            # if we consumed all the positionals we could and we're not
            # at the index of an option string, there were extra arguments
            if start_index not in option_string_indices:
                strings = arg_strings[start_index:next_option_string_index]
                extras.extend(strings)
                start_index = next_option_string_index

            # consume the next optional and any arguments for it
            start_index = consume_optional(start_index)

        # consume any positionals following the last Optional
        stop_index = consume_positionals(start_index)

        # if we didn't consume all the argument strings, there were extras
        extras.extend(arg_strings[stop_index:])

        # make sure all required actions were present and also convert
        # action defaults which were not given as arguments
        required_actions = []
        for action in self._actions:
            if action not in seen_actions:
                if action.required:
                    required_actions.append(argparse._get_action_name(action))
                else:
                    # Convert action default now instead of doing it before
                    # parsing arguments to avoid calling convert functions
                    # twice (which may fail) if the argument was given, but
                    # only if it was defined already in the namespace
                    if (
                        action.default is not None
                        and isinstance(action.default, str)
                        and hasattr(namespace, action.dest)
                        and action.default is getattr(namespace, action.dest)
                    ):
                        setattr(
                            namespace,
                            action.dest,
                            self._get_value(action, action.default),
                        )

        if required_actions:
            self.error(
                _("the following arguments are required: %s")
                % ", ".join(required_actions)
            )

        # make sure all required groups had one option present
        for group in self._mutually_exclusive_groups:
            if group.required:
                for action in group._group_actions:
                    if action in seen_non_default_actions:
                        break

                # if no actions were used, report the error
                else:
                    names = [
                        argparse._get_action_name(action)
                        for action in group._group_actions
                        if action.help is not argparse.SUPPRESS
                    ]
                    msg = _("one of the arguments %s is required")
                    self.error(msg % " ".join(names))  # type: ignore

        # return the updated namespace and the extra arguments
        return namespace, extras

    @override
    def error(self, message: str) -> NoReturn:
        """Improve error messages from argparse.

        error(message: string)

        Prints a usage message incorporating the message to stderr and
        exits.

        If you override this in a subclass, it should not return -- it
        should either exit or raise an exception.
        """

        extra_info: List[fmt.Element | str] = []
        message_title = "Parsing error"
        message_fmt = message

        if len(global_unrecognized_arg_and_prog) > 0:
            message_title = "Unrecognized options"
            message_fmt = fmt.text(
                f"Unrecognized options: {' '.join([arg for arg, _ in global_unrecognized_arg_and_prog])}"
            )
            unrecognized_arguments = set(
                arg
                for arg, _ in global_unrecognized_arg_and_prog
                # If we pass in `--spell-chekc on`, we only want `spell-chekc` and not
                # `on`.
                if arg.startswith("--")
            )
            arguments, has_subcommands, same_exists = recursive_arg_search(
                args=self._args,
                parser_spec=self._parser_specification,
                prog=self.prog.partition(" ")[0],
                unrecognized_arguments=unrecognized_arguments,
            )

            if has_subcommands and same_exists:
                message_fmt = fmt.text("Unrecognized or misplaced options:\n\n")
                for arg, prog in global_unrecognized_arg_and_prog:
                    message_fmt += fmt.text(
                        f"  {arg} (applied to ", fmt.text["green"](prog), ")\n"
                    )
                message_fmt += "\nArguments are applied to the directly preceding subcommand, so ordering matters."

            # Show similar arguments for keyword options.
            for unrecognized_argument in unrecognized_arguments:
                # Sort arguments by similarity.
                scored_arguments: List[Tuple[_ArgumentInfo, float]] = []
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
                prev_arg_option_strings: Optional[Tuple[str, ...]] = None
                show_arguments: List[_ArgumentInfo] = []
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

                prev_arg_info: Optional[_ArgumentInfo] = None
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
                                fmt.columns(
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
                            fmt.columns(
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

                    # Uncomment to show similarity metric.
                    # extra_info.append(
                    #     Padding(
                    #         f"[green]Similarity: {score:.02f}[/green]", (0, 0, 0, 8)
                    #     )
                    # )

                    helptext = generate_argument_helptext(
                        arg_info.arg, arg_info.arg.lowered
                    )
                    if helptext is not None and (
                        # Only print help messages if it's not the same as the previous
                        # one.
                        prev_arg_info is None
                        or arg_info.help != prev_arg_info.help
                        or arg_info.option_strings != prev_arg_info.option_strings
                        or arg_info.metavar != prev_arg_info.metavar
                    ):
                        extra_info.append(fmt.columns(("", 8), helptext))

                    # Show the subcommand that this argument is available in.
                    if has_subcommands:
                        extra_info.append(
                            fmt.columns(
                                ("", 8),
                                fmt.text("in ", fmt.text["green"](arg_info.usage_hint)),
                            )
                        )

                    prev_arg_info = arg_info

        elif message.startswith("the following arguments are required:"):
            message_title = "Required options"

            info_from_required_arg: Dict[str, Optional[_ArgumentInfo]] = {}
            for arg in message.partition(":")[2].strip().split(", "):
                if "/" in arg:
                    arg = arg.split("/")[0]
                info_from_required_arg[arg] = None

            arguments, has_subcommands, same_exists = recursive_arg_search(
                args=self._args,
                parser_spec=self._parser_specification,
                prog=self.prog.partition(" ")[0],
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
                    fmt.columns(
                        ("", 4),
                        fmt.text["bold"](maybe_arg.arg.get_invocation_text()[1]),
                    )
                )
                helptext = generate_argument_helptext(
                    maybe_arg.arg, maybe_arg.arg.lowered
                )
                if len(helptext) > 0:
                    extra_info.append(fmt.columns(("", 8), helptext))
                if has_subcommands:
                    # We are explicit about where the argument helptext is being
                    # extracted from because the `subcommand_match_score` heuristic
                    # above is flawed.
                    #
                    # The stars really need to be aligned for it to fail, but this makes
                    # sure that if it does fail that it's obvious to the user.
                    extra_info.append(
                        fmt.columns(
                            ("", 12),
                            fmt.text("in ", fmt.text["green"](maybe_arg.usage_hint)),
                        )
                    )

        if self._console_outputs:
            print(
                fmt.box["red"](
                    fmt.text["red", "bold"](message_title),
                    fmt.rows(
                        message_fmt,
                        *extra_info,
                        fmt.hr["red"](),
                        fmt.text(
                            "For full helptext, run ",
                            fmt.text["bold"](self.prog + " --help"),
                        ),
                    ),
                ),
                file=sys.stderr,
                flush=True,
            )
        sys.exit(2)
