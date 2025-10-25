"""Custom backend for parsing command-line arguments directly from ParserSpecification.

This backend bypasses argparse entirely and parses arguments directly using the
ParserSpecification. This can be significantly faster for complex command structures
with many subcommands.
"""

from __future__ import annotations

import itertools
import sys
import warnings
from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable, Sequence, cast

from tyro.conf._markers import CascadingSubcommandArgs

from .. import _arguments, _parsers, _strings, conf
from . import _help_formatting
from ._argparse_formatter import TyroArgumentParser
from ._base import ParserBackend


class KwargMap:
    """Look-up table for tracking keyword arguments. Due to aliases, each
    argument can have multiple string representations, like -v and
    --verbose."""

    def __init__(self) -> None:
        self._arg_from_kwarg: dict[str, _arguments.ArgumentDefinition] = {}
        self._value_from_boolean_flag: dict[str, bool] = {}
        self._arg_from_dest: dict[str | None, _arguments.ArgumentDefinition] = {}

    def args(self) -> Iterable[_arguments.ArgumentDefinition]:
        return self._arg_from_dest.values()

    def contains(self, kwarg: str) -> bool:
        return kwarg in self._arg_from_kwarg

    def get_kwarg(self, kwarg: str) -> _arguments.ArgumentDefinition | None:
        return self._arg_from_kwarg.get(kwarg, None)

    def push(self, arg: _arguments.ArgumentDefinition) -> None:
        self._arg_from_dest[arg.lowered.dest] = arg
        for kwarg in arg.lowered.name_or_flags:
            assert kwarg not in self._arg_from_kwarg, "Name conflict"
            self._arg_from_kwarg[kwarg] = arg

            if arg.lowered.action == "store_true":
                self._value_from_boolean_flag[kwarg] = True
            elif arg.lowered.action == "store_false":
                self._value_from_boolean_flag[kwarg] = False
            elif arg.lowered.action == "boolean_optional_action":
                self._value_from_boolean_flag[kwarg] = True
                inv_kwarg = _arguments.flag_to_inverse(kwarg)
                self._value_from_boolean_flag[inv_kwarg] = True
                assert inv_kwarg not in self._arg_from_kwarg, "Name conflict"
                self._arg_from_kwarg[inv_kwarg] = arg

    def get_boolean_value(self, kwarg: str) -> bool | None:
        return self._value_from_boolean_flag.get(kwarg, None)

    def pop(self, arg: _arguments.ArgumentDefinition) -> _arguments.ArgumentDefinition:
        self._arg_from_dest.pop(arg.lowered.dest)
        for kwarg_ in arg.lowered.name_or_flags:
            self._arg_from_kwarg.pop(kwarg_)
            if arg.lowered.action == "store_true":
                self._value_from_boolean_flag.pop(kwarg_)
            elif arg.lowered.action == "store_false":
                self._value_from_boolean_flag.pop(kwarg_)
            elif arg.lowered.action == "boolean_optional_action":
                inv_kwarg_ = _arguments.flag_to_inverse(kwarg_)
                self._arg_from_kwarg.pop(inv_kwarg_)
                self._value_from_boolean_flag.pop(kwarg_)
                self._value_from_boolean_flag.pop(inv_kwarg_)
        return arg


@dataclass
class TyroBackend(ParserBackend):
    """Backend that parses arguments directly from ParserSpecification.

    This implementation avoids the overhead of constructing an argparse parser,
    which can be significant for complex command structures with many subcommands.
    It parses command-line arguments directly using the ParserSpecification tree.
    """

    def parse_args(
        self,
        parser_spec: _parsers.ParserSpecification,
        args: Sequence[str],
        prog: str,
        return_unknown_args: bool,
        console_outputs: bool,
    ) -> tuple[dict[str | None, Any], list[str] | None]:
        """Parse command-line arguments directly from the specification."""

        out, unknown_args_and_progs = self._parse_args_recursive(
            parser_spec,
            args,
            prog,
            console_outputs=console_outputs,
        )
        if return_unknown_args:
            return out, [x[0] for x in unknown_args_and_progs]
        else:
            if len(unknown_args_and_progs) > 0:
                _help_formatting.unrecognized_args_error(
                    prog=prog,
                    unrecognized_args_and_progs=unknown_args_and_progs,
                    args=list(args),
                    parser_spec=parser_spec,
                    console_outputs=console_outputs,
                )
            return out, None

    def _parse_args_recursive(
        self,
        parser_spec: _parsers.ParserSpecification,
        args: Sequence[str],
        prog: str,
        console_outputs: bool,
    ) -> tuple[dict[str | None, Any], list[tuple[str, str]]]:
        # We'll start by setting up global values that persist across recursive calls.
        output: dict[str | None, Any] = {}
        unknown_args_and_progs: list[tuple[str, str]] = []
        subparser_frontier: dict[str, _parsers.SubparsersSpecification] = {}

        # Positional
        kwarg_map = KwargMap()
        positional_args: deque[_arguments.ArgumentDefinition] = deque()

        args_deque: deque[str] = deque(args)
        required_mutex_flags: dict[conf._mutex_group._MutexGroupConfig, list[str]] = {}

        def _recurse(parser_spec: _parsers.ParserSpecification) -> None:
            # Update the subparser frontier.
            subparser_frontier.update(parser_spec.subparsers_from_intern_prefix)

            # Register arguments in this parser level.
            for short_counter_arg in parser_spec.get_args_including_children():
                if short_counter_arg.is_suppressed():
                    continue

                # Update flag list for mutex group.
                mutex_group = short_counter_arg.field.mutex_group
                if mutex_group is not None and mutex_group.required:
                    required_mutex_flags.setdefault(mutex_group, []).append(
                        short_counter_arg.lowered.name_or_flags[0]
                    )

                # Default value for special action types.
                if short_counter_arg.lowered.action == "append":
                    output[
                        short_counter_arg.lowered.name_or_flags[-1]
                        if short_counter_arg.is_positional()
                        else short_counter_arg.lowered.dest
                    ] = []
                elif short_counter_arg.lowered.action == "count":
                    output[short_counter_arg.lowered.dest] = 0

                # Register argument.
                if short_counter_arg.is_positional():
                    positional_args.append(short_counter_arg)
                else:
                    kwarg_map.push(short_counter_arg)

            # Consume strings and use them to populate the output dict.
            while len(args_deque) > 0:
                arg_value = args_deque.popleft()

                # Helptext.
                if arg_value in ("-h", "--help") and parser_spec.add_help:
                    if console_outputs:
                        print(
                            *_help_formatting.format_help(
                                prog=prog if prog is not None else sys.argv[0],
                                description=parser_spec.description,
                                parser_specs=[parser_spec],
                                subparser_frontier=subparser_frontier,
                                is_root=parser_spec.intern_prefix == "",
                            ),
                            sep="\n",
                        )
                    sys.exit(0)

                # Handle assignments formatted as --flag=value.
                if arg_value.startswith("-") and "=" in arg_value:
                    maybe_flag, _, value = arg_value.partition("=")
                    if kwarg_map.contains(maybe_flag):
                        # This should also handle nargs!=1 cases like tuple[int, int].
                        # ["--tuple=1", "2"] will be broken into ["--tuple", "1", "2"].
                        args_deque.appendleft(value)
                        args_deque.appendleft(maybe_flag)
                        continue

                # Check for subparsers in the frontier.
                subparser_found = False
                subparser_found_prefix = None
                for intern_prefix, subparser_spec in subparser_frontier.items():
                    if arg_value in subparser_spec.parser_from_name:
                        subparser_found = True
                        subparser_found_prefix = intern_prefix
                        break
                if subparser_found:
                    assert subparser_found_prefix is not None
                    subparser_spec = subparser_frontier.pop(subparser_found_prefix)
                    _recurse(subparser_spec.parser_from_name[arg_value])
                    break

                # Handle normal flags.
                short_counter_arg = kwarg_map.get_kwarg(arg_value[:2])
                boolean_value = kwarg_map.get_boolean_value(arg_value)
                full_arg = kwarg_map.get_kwarg(arg_value)
                if (
                    short_counter_arg is not None
                    and short_counter_arg.lowered.action == "count"
                    and arg_value == arg_value[:2] + (len(arg_value) - 2) * arg_value[1]
                ):
                    dest = short_counter_arg.lowered.dest
                    output[dest] = cast(int, output[dest]) + len(arg_value) - 1
                    kwarg_map.pop(short_counter_arg)
                    continue
                elif boolean_value is not None:
                    assert full_arg is not None
                    output[full_arg.lowered.dest] = boolean_value
                    kwarg_map.pop(full_arg)
                    continue
                elif full_arg is not None:
                    # Counter argument.
                    if full_arg.lowered.action == "count":
                        dest = full_arg.lowered.dest
                        output[dest] = cast(int, output[dest]) + 1
                        continue

                    # Standard kwarg.
                    dest = full_arg.lowered.dest
                    self._consume_argument(
                        full_arg,
                        args_deque,
                        output,
                        kwarg_map,
                        subparser_frontier,
                        prog,
                        add_help=parser_spec.add_help,
                        console_outputs=console_outputs,
                    )
                    kwarg_map.pop(full_arg)
                    continue

                # Handle positional arguments.
                if len(positional_args) > 0:
                    arg = positional_args.popleft()
                    assert arg.lowered.dest is None
                    dest = arg.lowered.name_or_flags[-1]
                    self._consume_argument(
                        arg,
                        args_deque,
                        output,
                        kwarg_map,
                        subparser_frontier,
                        prog,
                        add_help=parser_spec.add_help,
                        console_outputs=console_outputs,
                    )
                    continue

                # If we reach here, we have an unknown argument.
                unknown_args_and_progs.append((arg_value, prog))

        _recurse(parser_spec)

        # Handle default subcommands for frontier groups.
        for intern_prefix, subparser_spec in subparser_frontier.items():
            dest = _strings.make_subparser_dest(intern_prefix)
            if dest not in output:
                # No subcommand was selected for this group.
                if subparser_spec.default_name is None:
                    # No default available; this is an error.
                    _help_formatting.error_and_exit(
                        "Missing subcommand",
                        f"Expected subcommand from {list(subparser_spec.parser_from_name.keys())}, "
                        f"but found: {args_deque[0] if len(args_deque) > 0 else 'nothing'}.",
                        prog=prog,
                        console_outputs=console_outputs,
                        add_help=parser_spec.add_help,
                    )
                output[dest] = subparser_spec.default_name

        # Handle any missing/remaining arguments.
        missing_required_args: list[str] = []
        for arg in itertools.chain(positional_args, kwarg_map.args()):
            if arg.lowered.required is True:
                # Missing argument!
                assert arg.lowered.metavar is not None
                missing_required_args.append(
                    arg.lowered.metavar
                    if arg.is_positional()
                    else arg.lowered.name_or_flags[-1]
                )
            else:
                output[arg.lowered.dest] = arg.lowered.default

        if len(missing_required_args) > 0:
            # TODO: revisit required_args_error().
            _help_formatting.required_args_error(
                prog=prog,
                required_args=missing_required_args,
                args=list(args),
                parser_spec=parser_spec,
                console_outputs=console_outputs,
            )
        return output, unknown_args_and_progs

    @staticmethod
    def _consume_argument(
        arg: _arguments.ArgumentDefinition,
        args_deque: deque[str],
        output: dict[str | None, Any],
        kwarg_map: KwargMap,
        subparser_frontier: dict[str, _parsers.SubparsersSpecification],
        prog: str,
        add_help: bool,
        console_outputs: bool,
    ):
        arg_values: list[str] = []

        # Consume arguments based on nargs.
        # https://docs.python.org/3/library/argparse.html#nargs
        if isinstance(arg.lowered.nargs, int):
            for _ in range(arg.lowered.nargs):
                if len(args_deque) == 0:
                    _help_formatting.error_and_exit(
                        f"Missing value for argument '{arg.lowered.name_or_flags}'. "
                        f"Expected {arg.lowered.nargs} values.",
                        prog=prog,
                        console_outputs=console_outputs,
                        add_help=add_help,
                    )
                arg_values.append(args_deque.popleft())
        elif arg.lowered.nargs in ("+", "*", "?"):
            counter = 0
            while (
                len(args_deque) > 0
                # TODO: this doesn't consider counters, like -vvv.
                and not kwarg_map.contains(args_deque[0])
                # To match argparse behavior:
                # - When nargs are present, we assume any `--` flag is a valid argument.
                and not args_deque[0].startswith("--")
                # Don't break for the firs value, except for nargs=="?".
                and (arg.lowered.nargs != "?" or counter == 0)
                # Break if we reach a subparser. This diverges from
                # argparse's behavior slightly, which has tradeoffs...
                and (
                    not any(
                        args_deque[0] in group.parser_from_name
                        for group in subparser_frontier.values()
                    )
                    or arg.lowered.nargs
                    == "?"  # Don't break for nargs="?" to allow one value.
                    or (arg.lowered.nargs == "+" and counter == 0)
                )
            ):
                arg_values.append(args_deque.popleft())
                counter += 1
            if arg.lowered.nargs == "+" and counter == 0:
                _help_formatting.error_and_exit(
                    f"Missing value for argument '{arg.lowered.name_or_flags}'. "
                    f"Expected at least one value.",
                    prog=prog,
                    console_outputs=console_outputs,
                    add_help=add_help,
                )

        # If present: make sure arguments are in choices.
        if arg.lowered.choices is not None:
            for value in arg_values:
                if value not in arg.lowered.choices:
                    _help_formatting.error_and_exit(
                        "Invalid choice",
                        f"invalid choice '{value}' for argument '{arg.lowered.name_or_flags}'. "
                        f"Expected one of {arg.lowered.choices}.",
                        prog=prog,
                        console_outputs=console_outputs,
                        add_help=add_help,
                    )

        # Populate output.
        dest = arg.lowered.dest
        if arg.lowered.action == "append":
            cast(list, output[dest]).append(arg_values)
        elif arg.lowered.nargs == "?" and len(arg_values) == 1:
            # Special case for nargs="?"; this is matched in _calling.py.
            output[dest] = arg_values[0]
        else:
            output[dest] = arg_values

    def get_parser_for_completion(
        self,
        parser_spec: _parsers.ParserSpecification,
        prog: str | None,
        add_help: bool,
    ) -> TyroArgumentParser:
        """Get an argparse parser for shell completion generation.

        Since shtab requires an argparse parser, we still need to create one
        for completion generation. This is only used when generating completions,
        not during normal parsing.
        """
        from ._argparse_backend import ArgparseBackend

        return ArgparseBackend().get_parser_for_completion(
            parser_spec, prog=prog, add_help=add_help
        )
