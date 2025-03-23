"""Utilities and functions for helptext formatting. We replace argparse's simple help
messages with ones that:
    - Are more nicely formatted!
    - Support multiple columns when many fields are defined.
    - Use `rich` for formatting.
    - Can be themed with an accent color.

This is largely built by fussing around in argparse implementation details. It's
chaotic as a result; for stability we mirror argparse at _argparse.py.
"""

from __future__ import annotations

import argparse as argparse_sys
import contextlib
import dataclasses
import difflib
import itertools
import re as _re
import shlex
import shutil
import sys
from gettext import gettext as _
from typing import (
    Any,
    Dict,
    Generator,
    Iterable,
    List,
    NoReturn,
    Optional,
    Set,
    Tuple,
)

from rich.columns import Columns
from rich.console import Console, Group, RenderableType
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from typing_extensions import override

from . import _argparse as argparse
from . import _arguments, _strings, conf
from ._parsers import ParserSpecification


@dataclasses.dataclass
class TyroTheme:
    border: Style = Style()
    description: Style = Style()
    invocation: Style = Style()
    metavar: Style = Style()
    metavar_fixed: Style = Style()
    helptext: Style = Style()
    helptext_required: Style = Style()
    helptext_default: Style = Style()

    def as_rich_theme(self) -> Theme:
        return Theme(vars(self))


def set_accent_color(accent_color: Optional[str]) -> None:
    """Set an accent color to use in help messages. Takes any color supported by ``rich``,
    see ``python -m rich.color``. Experimental."""
    THEME.border = Style(color=accent_color, dim=True)
    THEME.description = Style(color=accent_color, bold=True)
    THEME.invocation = Style()
    THEME.metavar = Style(color=accent_color, bold=True)
    THEME.metavar_fixed = Style(color="red", bold=True)
    THEME.helptext = Style(dim=True)
    THEME.helptext_required = Style(color="bright_red", bold=True)
    THEME.helptext_default = Style(
        color="cyan" if accent_color != "cyan" else "magenta"
        # Another option: make default color match accent color. This is maybe more
        # visually consistent, but harder to read.
        # color=accent_color if accent_color is not None else "cyan",
        # dim=accent_color is not None,
    )


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
                    option_strings,
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


# TODO: this is a prototype; for a v1.0.0 release we should revisit whether the global
# state here is acceptable or not.
THEME = TyroTheme()
set_accent_color(None)


def monkeypatch_len(obj: Any) -> int:
    if isinstance(obj, str):
        return len(_strings.strip_ansi_sequences(obj))
    else:
        return len(obj)


@contextlib.contextmanager
def ansi_context() -> Generator[None, None, None]:
    """Context for working with ANSI codes + argparse:
    - Applies a temporary monkey patch for making argparse ignore ANSI codes when
      wrapping usage text.
    - Enables support for Windows via colorama.
    """

    if not hasattr(argparse, "len"):
        # Sketchy, but seems to work.
        argparse.len = monkeypatch_len  # type: ignore
        try:  # pragma: no cover
            # Use Colorama to support coloring in Windows shells.
            import colorama  # type: ignore

            # Notes:
            #
            # (1) This context manager looks very nice and local, but under-the-hood
            # does some global operations which look likely to cause unexpected
            # behavior if another library relies on `colorama.init()` and
            # `colorama.deinit()`.
            #
            # (2) SSHed into a non-Windows machine from a WinAPI terminal => this
            # won't work.
            #
            # Fixing these issues doesn't seem worth it: it doesn't seem like there
            # are low-effort solutions for either problem, and more modern terminals
            # in Windows (PowerShell, MSYS2, ...) do support ANSI codes anyways.
            with colorama.colorama_text():
                yield

        except ImportError:
            yield

        del argparse.len  # type: ignore
    else:
        # No-op when the context manager is nested.
        yield


def str_from_rich(
    renderable: RenderableType, width: Optional[int] = None, soft_wrap: bool = False
) -> str:
    dummy_console = Console(width=width, theme=THEME.as_rich_theme())
    with dummy_console.capture() as out:
        dummy_console.print(renderable, soft_wrap=soft_wrap)
    return out.get().rstrip("\n")


@dataclasses.dataclass(frozen=True)
class _ArgumentInfo:
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

        extra_info: List[RenderableType] = []
        message_title = "Parsing error"

        if len(global_unrecognized_arg_and_prog) > 0:
            message_title = "Unrecognized options"
            message = f"Unrecognized options: {' '.join([arg for arg, _ in global_unrecognized_arg_and_prog])}"
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
                message = "Unrecognized or misplaced options:\n\n"
                for arg, prog in global_unrecognized_arg_and_prog:
                    message += f"  {arg} (applied to [green]{prog}[/green])\n"
                message += "\nArguments are applied to the directly preceding subcommand, so ordering matters."

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
                    extra_info.append(Rule(style=Style(color="red")))
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
                                Padding(
                                    "[...]",
                                    (0, 0, 0, 12),
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
                            Padding(
                                "[bold]"
                                + (
                                    ", ".join(arg_info.option_strings)
                                    if arg_info.metavar is None
                                    else ", ".join(arg_info.option_strings)
                                    + " "
                                    + arg_info.metavar
                                )
                                + "[/bold]",
                                (0, 0, 0, 4),
                            )
                        )

                    # Uncomment to show similarity metric.
                    # extra_info.append(
                    #     Padding(
                    #         f"[green]Similarity: {score:.02f}[/green]", (0, 0, 0, 8)
                    #     )
                    # )

                    if arg_info.help is not None and (
                        # Only print help messages if it's not the same as the previous
                        # one.
                        prev_arg_info is None
                        or arg_info.help != prev_arg_info.help
                        or arg_info.option_strings != prev_arg_info.option_strings
                        or arg_info.metavar != prev_arg_info.metavar
                    ):
                        extra_info.append(Padding(arg_info.help, (0, 0, 0, 8)))

                    # Show the subcommand that this argument is available in.
                    if has_subcommands:
                        extra_info.append(
                            Padding(
                                f"in [green]{arg_info.usage_hint}[/green]",
                                (0, 0, 0, 12),
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
                            Rule(style=Style(color="red")),
                            "Argument helptext:",
                        ]
                    )
                    first = False

                extra_info.append(
                    Padding(
                        "[bold]"
                        + (
                            ", ".join(maybe_arg.option_strings)
                            if maybe_arg.metavar is None
                            else ", ".join(maybe_arg.option_strings)
                            + " "
                            + maybe_arg.metavar
                        )
                        + "[/bold]",
                        (0, 0, 0, 4),
                    )
                )
                if maybe_arg.help is not None:
                    extra_info.append(Padding(maybe_arg.help, (0, 0, 0, 8)))
                if has_subcommands:
                    # We are explicit about where the argument helptext is being
                    # extracted from because the `subcommand_match_score` heuristic
                    # above is flawed.
                    #
                    # The stars really need to be aligned for it to fail, but this makes
                    # sure that if it does fail that it's obvious to the user.
                    extra_info.append(
                        Padding(
                            f"in [green]{maybe_arg.usage_hint}[/green]",
                            (0, 0, 0, 12),
                        )
                    )

        if self._console_outputs:
            console = Console(theme=THEME.as_rich_theme(), stderr=True)
            console.print(
                Panel(
                    Group(
                        (
                            f"{message[0].upper() + message[1:]}"
                            if len(message) > 0
                            else ""
                        ),
                        *extra_info,
                        Rule(style=Style(color="red")),
                        f"For full helptext, run [bold]{self.prog} --help[/bold]",
                    ),
                    title=f"[bold]{message_title}[/bold]",
                    title_align="left",
                    border_style=Style(color="bright_red"),
                    expand=False,
                )
            )
        sys.exit(2)


class TyroArgparseHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def __init__(self, prog: str):
        indent_increment = 4
        width = shutil.get_terminal_size().columns - 2
        max_help_position = 24
        self._fixed_help_position = False

        # TODO: hacky. Refactor this.
        self._strip_ansi_sequences = not _arguments.USE_RICH

        super().__init__(prog, indent_increment, max_help_position, width)

    @override
    def _format_args(self, action, default_metavar):
        """Override _format_args() to ignore nargs and always expect single string
        metavars."""
        get_metavar = self._metavar_formatter(action, default_metavar)

        out = get_metavar(1)[0]
        if isinstance(out, str):
            # Can result in an failed argparse assertion if we turn off soft wrapping.
            return (
                out
                if self._strip_ansi_sequences
                else str_from_rich(
                    Text.from_ansi(
                        out,
                        style=(
                            THEME.metavar_fixed if out == "{fixed}" else THEME.metavar
                        ),
                        overflow="fold",
                    ),
                    soft_wrap=True,
                )
            )
        return out

    @override
    def add_argument(self, action):  # pragma: no cover
        # Patch to avoid super long arguments from shifting the helptext of all of the
        # fields.
        prev_max_length = self._action_max_length
        super().add_argument(action)
        if self._action_max_length > self._max_help_position + 2:
            self._action_max_length = prev_max_length

    def _split_lines(self, text, width):  # pragma: no cover
        text = self._whitespace_matcher.sub(" ", text).strip()
        # The textwrap module is used only for formatting help.
        # Delay its import for speeding up the common usage of argparse.
        import textwrap as textwrap

        # Sketchy, but seems to work.
        textwrap.len = monkeypatch_len  # type: ignore
        out = textwrap.wrap(text, width)
        del textwrap.len  # type: ignore
        return out

    @override
    def _fill_text(self, text, width, indent):
        return "".join(indent + line for line in text.splitlines(keepends=True))

    @override
    def format_help(self):
        # Try with and without a fixed help position, then return the shorter help
        # message.
        # For dense multi-column layouts, the fixed help position is often shorter.
        # For wider layouts, using the default help position settings can be more
        # efficient.
        self._tyro_rule = None
        self._fixed_help_position = False
        help1 = super().format_help()

        self._tyro_rule = None
        self._fixed_help_position = True
        help2 = super().format_help()

        out = help1 if help1.count("\n") < help2.count("\n") else help2

        if self._strip_ansi_sequences:
            return _strings.strip_ansi_sequences(out)
        else:
            return out

    @override
    class _Section(object):  # type: ignore
        def __init__(self, formatter, parent, heading=None):
            self.formatter = formatter
            self.parent = parent
            self.heading = heading
            self.items = []
            self.formatter._tyro_rule = None

        def format_help(self):
            if self.parent is None:
                return self._tyro_format_root()
            else:
                return self._tyro_format_nonroot()

        def _tyro_format_root(self):
            dummy_console = Console(
                width=self.formatter._width, theme=THEME.as_rich_theme()
            )
            with dummy_console.capture() as capture:
                # Get rich renderables from items.
                top_parts = []
                column_parts = []
                column_parts_lines = []
                for func, args in self.items:
                    item_content = func(*args)
                    if item_content is None:
                        pass

                    # Add strings. (usage, description, etc)
                    elif isinstance(item_content, str):
                        if item_content.strip() == "":
                            continue
                        top_parts.append(Text.from_ansi(item_content, overflow="fold"))

                    # Add panels. (argument groups, subcommands, etc)
                    else:
                        assert isinstance(item_content, Panel)
                        column_parts.append(item_content)
                        # Estimate line count. This won't correctly account for
                        # wrapping, as we don't know the column layout yet.
                        column_parts_lines.append(
                            str_from_rich(item_content, width=65).strip().count("\n")
                            + 1
                        )

                # Split into columns.
                min_column_width = 65
                height_breakpoint = 50
                column_count = max(
                    1,
                    min(
                        sum(column_parts_lines) // height_breakpoint + 1,
                        self.formatter._width // min_column_width,
                        len(column_parts),
                    ),
                )
                done = False
                column_parts_grouped = None
                column_width = None
                while not done:
                    if column_count > 1:  # pragma: no cover
                        column_width = self.formatter._width // column_count - 1
                        # Correct the line count for each panel using the known column
                        # width. This will account for word wrap.
                        column_parts_lines = [
                            str_from_rich(p, width=column_width).strip().count("\n") + 1
                            for p in column_parts
                        ]
                    else:
                        column_width = None

                    column_lines = [0 for i in range(column_count)]
                    column_parts_grouped = [[] for i in range(column_count)]
                    for p, l in zip(column_parts, column_parts_lines):
                        chosen_column = column_lines.index(min(column_lines))
                        column_parts_grouped[chosen_column].append(p)
                        column_lines[chosen_column] += l

                    column_lines_max = max(*column_lines, 1)  # Prevent divide-by-zero.
                    column_lines_ratio = [l / column_lines_max for l in column_lines]

                    # Done if we're down to one column or all columns are
                    # within 60% of the maximum height.
                    #
                    # We use these ratios to prevent large hanging columns: https://github.com/brentyi/tyro/issues/222
                    if column_count == 1 or all(
                        [ratio > 0.6 for ratio in column_lines_ratio]
                    ):
                        break
                    column_count -= 1  # pragma: no cover

                assert column_parts_grouped is not None
                columns = Columns(
                    [Group(*g) for g in column_parts_grouped],
                    column_first=True,
                    width=column_width,
                )

                dummy_console.print(Group(*top_parts))
                dummy_console.print(columns)
            return capture.get()

        def _format_action(self, action: argparse.Action):
            invocation = self.formatter._format_action_invocation(action)
            indent = self.formatter._current_indent
            help_position = min(
                self.formatter._action_max_length + 4,
                self.formatter._max_help_position,
            )
            if self.formatter._fixed_help_position:
                help_position = 4

            item_parts: List[RenderableType] = []

            # Put invocation and help side-by-side.
            if action.option_strings == ["-h", "--help"]:
                # Darken helptext for --help flag. This makes it visually consistent
                # with the helptext strings defined via docstrings and set by
                # _arguments.py.
                assert action.help is not None
                action.help = str_from_rich(
                    Text.from_markup("[helptext]" + action.help + "[/helptext]")
                )

            # Unescape % signs, which need special handling in argparse.
            if action.help is not None:
                assert isinstance(action.help, str)
                helptext = (
                    Text.from_ansi(action.help.replace("%%", "%"), overflow="fold")
                    if _strings.strip_ansi_sequences(action.help) != action.help
                    else Text.from_markup(
                        action.help.replace("%%", "%"), overflow="fold"
                    )
                )
            else:
                helptext = Text("")

            if (
                action.help
                and len(_strings.strip_ansi_sequences(invocation)) + indent
                < help_position - 1
                and not self.formatter._fixed_help_position
            ):
                table = Table(show_header=False, box=None, padding=0)
                table.add_column(width=help_position - indent)
                table.add_column()
                table.add_row(
                    Text.from_ansi(
                        invocation,
                        style=THEME.invocation,
                        overflow="fold",
                    ),
                    helptext,
                )
                item_parts.append(table)

            # Put invocation and help on separate lines.
            else:
                item_parts.append(
                    Text.from_ansi(
                        invocation + "\n",
                        style=THEME.invocation,
                        overflow="fold",
                    )
                )
                if action.help:
                    item_parts.append(
                        Padding(
                            # Unescape % signs, which need special handling in argparse.
                            helptext,
                            pad=(0, 0, 0, help_position - indent),
                        )
                    )

            # Add subactions, indented.
            try:
                subaction: argparse.Action
                for subaction in action._get_subactions():  # type: ignore
                    self.formatter._indent()
                    item_parts.append(
                        Padding(
                            Group(*self._format_action(subaction)),
                            pad=(0, 0, 0, self.formatter._indent_increment),
                        )
                    )
                    self.formatter._dedent()
            except AttributeError:
                pass

            return item_parts

        def _tyro_format_nonroot(self):
            # Add each child item as a rich renderable.
            description_part = None
            item_parts = []
            for func, args in self.items:
                if (
                    getattr(func, "__func__", None)
                    is TyroArgparseHelpFormatter._format_action
                ):
                    (action,) = args
                    assert isinstance(action, argparse.Action)
                    item_parts.extend(self._format_action(action))

                else:
                    item_content = func(*args)
                    assert isinstance(item_content, str)
                    if item_content.strip() != "":
                        assert (
                            description_part is None
                        )  # Should only have one description part.
                        description_part = Text.from_ansi(
                            item_content.strip() + "\n",
                            style=THEME.description,
                            overflow="fold",
                        )

            if len(item_parts) == 0:
                return None

            # Get heading.
            if self.heading is not argparse.SUPPRESS and self.heading is not None:
                current_indent = self.formatter._current_indent
                heading = "%*s%s:\n" % (current_indent, "", self.heading)
                # Remove colon from heading.
                heading = heading.strip()[:-1]
            else:
                heading = ""

            # Determine width for divider below description text. This is shared across
            # all sections in a particular formatter.
            lines = list(
                itertools.chain(
                    *map(
                        lambda p: _strings.strip_ansi_sequences(
                            str_from_rich(
                                p, width=self.formatter._width, soft_wrap=True
                            )
                        )
                        .rstrip()
                        .split("\n"),
                        (
                            item_parts + [description_part]
                            if description_part is not None
                            else item_parts
                        ),
                    )
                )
            )
            max_width = max(map(len, lines))

            if self.formatter._tyro_rule is None:
                # We don't use rich.rule.Rule() because this will make all of the panels
                # expand to fill the full width of the console. This only impacts
                # single-column layouts.
                self.formatter._tyro_rule = Text.from_ansi(
                    "─" * max_width, style=THEME.border, overflow="crop"
                )
            elif len(self.formatter._tyro_rule._text[0]) < max_width:
                self.formatter._tyro_rule._text = ["─" * max_width]

            # Add description text if needed.
            if description_part is not None:
                item_parts = [
                    description_part,
                    self.formatter._tyro_rule,
                ] + item_parts

            return Panel(
                Group(*item_parts),
                title=heading,
                title_align="left",
                border_style=THEME.border,
                # padding=(1, 1, 0, 1),
            )

    def _format_actions_usage(self, actions, groups):  #  pragma: no cover
        """Backporting from Python 3.10, primarily to call format_usage() on actions."""

        # find group indices and identify actions in groups
        group_actions = set()
        inserts = {}
        for group in groups:
            if not group._group_actions:
                raise ValueError(f"empty group {group}")

            try:
                start = actions.index(group._group_actions[0])  # type: ignore
            except ValueError:
                continue
            else:
                group_action_count = len(group._group_actions)
                end = start + group_action_count
                if actions[start:end] == group._group_actions:  # type: ignore
                    suppressed_actions_count = 0
                    for action in group._group_actions:
                        group_actions.add(action)
                        if action.help is argparse.SUPPRESS:
                            suppressed_actions_count += 1

                    exposed_actions_count = (
                        group_action_count - suppressed_actions_count
                    )

                    if not group.required:  # type: ignore
                        if start in inserts:
                            inserts[start] += " ["
                        else:
                            inserts[start] = "["
                        if end in inserts:
                            inserts[end] += "]"
                        else:
                            inserts[end] = "]"
                    elif exposed_actions_count > 1:
                        if start in inserts:
                            inserts[start] += " ("
                        else:
                            inserts[start] = "("
                        if end in inserts:
                            inserts[end] += ")"
                        else:
                            inserts[end] = ")"
                    for i in range(start + 1, end):
                        inserts[i] = "|"

        # collect all actions format strings
        parts = []
        for i, action in enumerate(actions):
            # suppressed arguments are marked with None
            # remove | separators for suppressed arguments
            if action.help is argparse.SUPPRESS:
                parts.append(None)
                if inserts.get(i) == "|":
                    inserts.pop(i)
                elif inserts.get(i + 1) == "|":
                    inserts.pop(i + 1)

            # produce all arg strings
            elif not action.option_strings:
                default = self._get_default_metavar_for_positional(action)
                part = self._format_args(action, default)

                # if it's in a group, strip the outer []
                if action in group_actions:
                    if part[0] == "[" and part[-1] == "]":
                        part = part[1:-1]

                # add the action string to the list
                parts.append(part)

            # produce the first way to invoke the option in brackets
            else:
                option_string = action.option_strings[0]

                # if the Optional doesn't take a value, format is:
                #    -s or --long
                if action.nargs == 0:
                    part = (
                        action.format_usage()
                        if hasattr(action, "format_usage")
                        else "%s" % option_string
                    )

                # if the Optional takes a value, format is:
                #    -s ARGS or --long ARGS
                else:
                    default = self._get_default_metavar_for_optional(action)
                    args_string = self._format_args(action, default)
                    part = "%s %s" % (option_string, args_string)

                # make it look optional if it's not required or in a group
                if not action.required and action not in group_actions:
                    part = "[%s]" % part

                # add the action string to the list
                parts.append(part)

        # insert things at the necessary indices
        for i in sorted(inserts, reverse=True):
            parts[i:i] = [inserts[i]]

        # join all the action items with spaces
        text = " ".join([item for item in parts if item is not None])

        # clean up separators for mutually exclusive groups
        open = r"[\[(]"
        close = r"[\])]"
        text = _re.sub(r"(%s) " % open, r"\1", text)
        text = _re.sub(r" (%s)" % close, r"\1", text)
        text = _re.sub(r"%s *%s" % (open, close), r"", text)
        text = text.strip()

        # return the text
        return text

    @override
    def _format_usage(
        self, usage, actions: Iterable[argparse.Action], groups, prefix
    ) -> str:
        assert isinstance(actions, list)
        if len(actions) > 4:
            new_actions = []
            prog_parts = shlex.split(self._prog)
            added_options = False
            for action in actions:
                if action.dest == "help" or len(action.option_strings) == 0:
                    new_actions.append(action)
                elif not added_options:
                    added_options = True
                    new_actions.append(
                        argparse.Action(
                            [
                                (
                                    "OPTIONS"
                                    if len(prog_parts) == 1
                                    else prog_parts[-1].upper() + " OPTIONS"
                                )
                            ],
                            dest="",
                        )
                    )
            actions = new_actions

        # Format the usage label.
        if prefix is None:
            prefix = str_from_rich("[bold]usage[/bold]: ")
        usage = super()._format_usage(
            usage,
            actions,
            groups,
            prefix,
        )
        return "\n\n" + usage
