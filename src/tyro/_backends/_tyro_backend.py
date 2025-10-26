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
from . import _tyro_help_formatting
from ._argparse_formatter import TyroArgumentParser
from ._base import ParserBackend


class KwargMap:
    """Look-up table for tracking keyword arguments. Due to aliases, each
    argument can have multiple string representations, like -v and
    --verbose."""

    def __init__(self) -> None:
        self._arg_from_kwarg: dict[str, _arguments.ArgumentDefinition] = {}
        self._value_from_boolean_flag: dict[str, bool] = {}

        # This should be indexed with `arg.get_output_key()`, not
        # `arg.lowered.dest`. This is because `lowered.dest` is `None` for
        # positional arguments.
        self._arg_from_dest: dict[str | None, _arguments.ArgumentDefinition] = {}

    def args(self) -> Iterable[_arguments.ArgumentDefinition]:
        return self._arg_from_dest.values()

    def contains(self, kwarg: str) -> bool:
        return kwarg in self._arg_from_kwarg

    def get_kwarg(self, kwarg: str) -> _arguments.ArgumentDefinition | None:
        return self._arg_from_kwarg.get(kwarg, None)

    def push(self, arg: _arguments.ArgumentDefinition) -> None:
        self._arg_from_dest[arg.get_output_key()] = arg
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
                self._value_from_boolean_flag[inv_kwarg] = False
                assert inv_kwarg not in self._arg_from_kwarg, "Name conflict"
                self._arg_from_kwarg[inv_kwarg] = arg

    def get_boolean_value(self, kwarg: str) -> bool | None:
        return self._value_from_boolean_flag.get(kwarg, None)

    def pop(self, arg: _arguments.ArgumentDefinition) -> _arguments.ArgumentDefinition:
        self._arg_from_dest.pop(arg.get_output_key())
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
        add_help: bool,
    ) -> tuple[dict[str | None, Any], list[str] | None]:
        """Parse command-line arguments directly from the specification."""

        out, unknown_args_and_progs = self._parse_args_recursive(
            parser_spec,
            args,
            prog,
            console_outputs=console_outputs,
            add_help=add_help,
            return_unknown_args=return_unknown_args,
        )
        if return_unknown_args:
            return out, [x[0] for x in unknown_args_and_progs]
        else:
            # Error would have been caught earlier.
            assert len(unknown_args_and_progs) == 0
            return out, None

    def _parse_args_recursive(
        self,
        parser_spec: _parsers.ParserSpecification,
        args: Sequence[str],
        prog: str,
        console_outputs: bool,
        add_help: bool,
        return_unknown_args: bool,
    ) -> tuple[dict[str | None, Any], list[tuple[str, str]]]:
        # We'll start by setting up global values that persist across recursive calls.
        output: dict[str | None, Any] = {}
        unknown_args_and_progs: list[tuple[str, str]] = []
        subparser_frontier: dict[str, _parsers.SubparsersSpecification] = {}
        arg_ctx_from_dest: dict[str, _tyro_help_formatting.ArgWithContext] = {}

        cascaded_args: list[_tyro_help_formatting.ArgWithContext] = []

        kwarg_map = KwargMap()
        positional_args: deque[_arguments.ArgumentDefinition] = deque()

        args_deque: deque[str] = deque(args)

        # Helpers for enforcing mutex groups.
        required_mutex_args: dict[
            conf._mutex_group._MutexGroupConfig, list[_arguments.ArgumentDefinition]
        ] = {}
        observed_mutex_groups: dict[
            conf._mutex_group._MutexGroupConfig,
            tuple[str, _arguments.ArgumentDefinition],
        ] = {}

        def enforce_mutex_group(
            arg: _arguments.ArgumentDefinition | None, arg_str: str
        ) -> None:
            if arg is None or arg.field.mutex_group is None:
                return

            # TODO: write some tests for combining mutually exclusive positional and keyword args.
            if arg.field.mutex_group in observed_mutex_groups:
                existing_arg, existing_arg_str = observed_mutex_groups[
                    arg.field.mutex_group
                ]
                if existing_arg is not None and existing_arg != arg_str:
                    _tyro_help_formatting.error_and_exit(
                        "Mutually exclusive arguments",
                        f"Arguments {existing_arg_str} and {arg_str} are not allowed together!",
                        prog=prog,
                        console_outputs=console_outputs,
                        add_help=add_help,
                    )
            observed_mutex_groups[arg.field.mutex_group] = (arg_str, arg)

        def _recurse(parser_spec: _parsers.ParserSpecification) -> None:
            # Update the subparser frontier.
            subparser_frontier.update(parser_spec.subparsers_from_intern_prefix)
            local_args: list[_tyro_help_formatting.ArgWithContext] = []

            # Register arguments in this parser level.
            for arg in parser_spec.get_args_including_children():
                if arg.is_suppressed():
                    continue

                arg_ctx_from_dest[arg.get_output_key()] = (
                    _tyro_help_formatting.ArgWithContext(arg, parser_spec)
                )

                # Record in full arg list. This is used for helptext generation.
                (
                    cascaded_args
                    if CascadingSubcommandArgs in arg.field.markers
                    else local_args
                ).append(_tyro_help_formatting.ArgWithContext(arg, parser_spec))

                if arg.field.mutex_group is not None and arg.field.mutex_group.required:
                    required_mutex_args.setdefault(arg.field.mutex_group, []).append(
                        arg
                    )

                # Default value for special action types.
                if arg.lowered.action == "append":
                    output[
                        arg.lowered.name_or_flags[-1]
                        if arg.is_positional()
                        else arg.lowered.dest
                    ] = []
                elif arg.lowered.action == "count":
                    output[arg.lowered.dest] = 0

                # Register argument.
                if arg.is_positional():
                    if len(arg.lowered.name_or_flags) != 1:
                        warnings.warn(
                            f"Positional argument {arg.lowered.name_or_flags} "
                            "should have exactly one name.",
                            category=UserWarning,
                        )
                    positional_args.append(arg)
                else:
                    kwarg_map.push(arg)

            # Consume strings and use them to populate the output dict.
            subparser_found: _parsers.ParserSpecification | None = None
            args_to_pop: list[_arguments.ArgumentDefinition] = []
            while len(args_deque) > 0:
                arg_value = args_deque.popleft()

                # Helptext.
                if arg_value in ("-h", "--help") and add_help:
                    if console_outputs:
                        local_prog = (
                            prog
                            if parser_spec.prog_suffix == ""
                            else f"{prog} {parser_spec.prog_suffix}"
                        )
                        print(
                            *_tyro_help_formatting.format_help(
                                prog=local_prog,
                                parser_specs=[parser_spec],
                                subparser_frontier=subparser_frontier,
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
                intern_prefix = None
                for intern_prefix, subparser_spec in subparser_frontier.items():
                    if arg_value in subparser_spec.parser_from_name:
                        subparser_found = subparser_spec.parser_from_name[arg_value]
                        output[_strings.make_subparser_dest(intern_prefix)] = arg_value
                        break
                if subparser_found is not None:
                    assert intern_prefix is not None
                    subparser_frontier.pop(intern_prefix)
                    break

                # Handle normal flags.
                short_counter_arg = kwarg_map.get_kwarg(arg_value[:2])
                boolean_value = kwarg_map.get_boolean_value(arg_value)
                full_arg = kwarg_map.get_kwarg(arg_value)
                enforce_mutex_group(short_counter_arg, arg_value)
                enforce_mutex_group(full_arg, arg_value)
                if (
                    short_counter_arg is not None
                    and short_counter_arg.lowered.action == "count"
                    and arg_value == arg_value[:2] + (len(arg_value) - 2) * arg_value[1]
                ):
                    dest = short_counter_arg.lowered.dest
                    output[dest] = cast(int, output[dest]) + len(arg_value) - 1
                    args_to_pop.append(short_counter_arg)
                    continue
                elif boolean_value is not None:
                    assert full_arg is not None
                    output[full_arg.lowered.dest] = boolean_value
                    args_to_pop.append(full_arg)
                    continue
                elif full_arg is not None:
                    # Counter argument.
                    # TODO: add tests for counter arguments that are also
                    # marked as positional. The positional marker should be
                    # ignored.
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
                        add_help=add_help,
                        console_outputs=console_outputs,
                    )
                    args_to_pop.append(full_arg)
                    continue

                # Handle positional arguments.
                if len(positional_args) > 0:
                    arg = positional_args.popleft()
                    args_deque.appendleft(arg_value)
                    assert arg.lowered.dest is None
                    dest = arg.lowered.name_or_flags[-1]
                    self._consume_argument(
                        arg,
                        args_deque,
                        output,
                        kwarg_map,
                        subparser_frontier,
                        prog,
                        add_help=add_help,
                        console_outputs=console_outputs,
                    )
                    continue

                # If we reach here, we have an unknown argument.
                unknown_args_and_progs.append(
                    (
                        arg_value,
                        prog + " " + parser_spec.prog_suffix
                        if parser_spec.prog_suffix != ""
                        else prog,
                    )
                )

            # Pop parsed arguments. We de-duplicate using `dest`.
            for arg in {arg.lowered.dest: arg for arg in args_to_pop}.values():
                kwarg_map.pop(arg)

            # Process any missing arguments.
            missing_required_args: list[_tyro_help_formatting.ArgWithContext] = []
            for arg in tuple(positional_args) + tuple(kwarg_map.args()):
                if subparser_found and CascadingSubcommandArgs in arg.field.markers:
                    continue

                # Optional arguments.
                if (
                    not arg.lowered.required
                    or arg.lowered.nargs == "?"
                    or (
                        # For positional arguments, allow empty sequences.
                        arg.is_positional() and arg.lowered.nargs == "*"
                    )
                ) and arg.lowered.action != "count":
                    if arg.is_positional():
                        positional_args.remove(arg)
                    else:
                        kwarg_map.pop(arg)
                    output[arg.get_output_key()] = arg.lowered.default
                else:
                    missing_required_args.append(
                        arg_ctx_from_dest[arg.get_output_key()]
                    )
            if len(missing_required_args) > 0:
                _tyro_help_formatting.required_args_error(
                    prog=prog,
                    required_args=missing_required_args,
                    unrecognized_args_and_progs=unknown_args_and_progs,
                    console_outputs=console_outputs,
                    add_help=add_help,
                )

            # Parse arguments for subparser.
            if subparser_found:
                _recurse(
                    subparser_found,
                )

        _recurse(parser_spec)

        # Handle any missing/remaining arguments.
        def _check_for_missing_args() -> None:
            missing_required_args: list[_tyro_help_formatting.ArgWithContext] = []
            missing_mutex_groups = set(required_mutex_args.keys()) - set(
                observed_mutex_groups.keys()
            )
            for missing_group in missing_mutex_groups:
                missing_required_args.append(
                    arg_ctx_from_dest[
                        required_mutex_args[missing_group][0].get_output_key()
                    ]
                )
            for arg in itertools.chain(positional_args, kwarg_map.args()):
                if arg.lowered.required:
                    missing_required_args.append(
                        arg_ctx_from_dest[arg.get_output_key()]
                    )

            if len(missing_required_args) > 0:
                _tyro_help_formatting.required_args_error(
                    prog=prog,
                    required_args=missing_required_args,
                    unrecognized_args_and_progs=unknown_args_and_progs,
                    console_outputs=console_outputs,
                    add_help=add_help,
                )

        _check_for_missing_args()

        # Catch unrecognized arguments.
        if not return_unknown_args and len(unknown_args_and_progs) > 0:
            _tyro_help_formatting.unrecognized_args_error(
                prog=prog,
                unrecognized_args_and_progs=unknown_args_and_progs,
                args=list(args),
                parser_spec=parser_spec,
                console_outputs=console_outputs,
                add_help=add_help,
            )

        # Handle default subcommands for frontier groups.
        # This may take multiple passes, because each default subcommand may
        # introduce more default subcommands.
        while len(subparser_frontier) > 0:
            for intern_prefix in tuple(subparser_frontier.keys()):
                dest = _strings.make_subparser_dest(intern_prefix)
                assert dest not in output
                subparser_spec = subparser_frontier.pop(intern_prefix)

                # No subcommand was selected for this group.
                if subparser_spec.default_name is None:
                    # No default available; this is an error.
                    _tyro_help_formatting.error_and_exit(
                        "Missing subcommand",
                        *[
                            f"Expected subcommand from {list(subparser_spec.parser_from_name.keys())}, "
                            f"but found: {args_deque[0]}.",
                        ]
                        if len(args_deque) > 0
                        else [
                            f"Expected subcommand from {list(subparser_spec.parser_from_name.keys())}."
                        ],
                        prog=prog,
                        console_outputs=console_outputs,
                        add_help=add_help,
                    )

                output[dest] = subparser_spec.default_name
                _recurse(subparser_spec.parser_from_name[subparser_spec.default_name])

        # Check second time for missing args; there are adversarial cases where
        # the default subcommand can have them via `tyro.MISSING`.
        _check_for_missing_args()

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
                    _tyro_help_formatting.error_and_exit(
                        "Missing argument",
                        f"Missing value for argument '{arg.lowered.name_or_flags}'. "
                        f"Expected {arg.lowered.nargs} values.",
                        prog=prog,
                        console_outputs=console_outputs,
                        add_help=add_help,
                    )
                arg_values.append(args_deque.popleft())
        elif arg.lowered.nargs in ("*", "?"):
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
                _tyro_help_formatting.error_and_exit(
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
                    _tyro_help_formatting.error_and_exit(
                        "Invalid choice",
                        f"invalid choice '{value}' for argument '{arg.lowered.name_or_flags}'. "
                        f"Expected one of {arg.lowered.choices}.",
                        prog=prog,
                        console_outputs=console_outputs,
                        add_help=add_help,
                    )

        # Populate output.
        dest = arg.get_output_key()
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
