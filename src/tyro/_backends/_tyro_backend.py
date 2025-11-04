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
from typing import Any, Iterable, Literal, Sequence, cast

from tyro.conf._markers import CascadeSubcommandArgs

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
        subparser_implicit_selectors: dict[str, set[str]] = {}

        arg_ctx_from_dest: dict[str, _parsers.ArgWithContext] = {}

        cascaded_args: list[_tyro_help_formatting.ArgWithContext] = []

        kwarg_map = KwargMap()
        positional_args: deque[_arguments.ArgumentDefinition] = deque()

        # Track implicit subcommand selections for better error messages.
        # Maps subcommand_name -> (selected_subcommand_name, trigger_flag).
        implicit_arg_from_subcommand_name: dict[str, tuple[str, str]] = {}

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

        def _get_selectors(
            subparser_spec: _parsers.SubparsersSpecification,
            out: set[str] | None = None,
        ) -> set[str]:
            if out is None:
                out = set()
            if subparser_spec.default_name is not None:
                default_parser = subparser_spec.parser_from_name[
                    subparser_spec.default_name
                ].evaluate()
                for arg_ctx in default_parser.get_args_including_children():
                    if arg_ctx.arg.is_positional():
                        continue
                    out.update(arg_ctx.arg.lowered.name_or_flags)
                for (
                    inner_name,
                    inner_subparsers,
                ) in default_parser.subparsers_from_intern_prefix.items():
                    # Add all the subcommand selector names from this level.
                    out.update(inner_subparsers.parser_from_name.keys())
                    # Recursively collect selectors from nested defaults.
                    _get_selectors(inner_subparsers, out=out)
            return out

        def _recurse(
            parser_spec: _parsers.ParserSpecification, local_prog: str
        ) -> None:
            # Update the subparser frontier.
            subparser_frontier.update(parser_spec.subparsers_from_intern_prefix)

            if CascadeSubcommandArgs in parser_spec.markers:
                for (
                    intern_prefix,
                    subparser_spec,
                ) in parser_spec.subparsers_from_intern_prefix.items():
                    subparser_implicit_selectors[intern_prefix] = (
                        _get_selectors(subparser_spec)
                        if subparser_spec.default_name is not None
                        else set()
                    )

            local_args: list[_tyro_help_formatting.ArgWithContext] = []

            # Register arguments in this parser level.
            for arg_ctx in parser_spec.get_args_including_children():
                arg = arg_ctx.arg
                if arg.is_suppressed():
                    continue

                arg_ctx_from_dest[arg.get_output_key()] = arg_ctx

                # Record in full arg list. This is used for helptext generation.
                (
                    cascaded_args
                    if CascadeSubcommandArgs in arg.field.markers
                    else local_args
                ).append(arg_ctx)

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
            subparser_found_name: str = ""
            args_to_pop: list[_arguments.ArgumentDefinition] = []
            while len(args_deque) > 0:
                arg_value = args_deque.popleft()

                # Support --flag_name for --flag-name by swapping delimiters.
                # Also extract the value if this is a --flag=value assignment.
                maybe_flag_delimeter_swapped: str
                equals_value: str | None = None

                if len(arg_value) > 2 and arg_value.startswith("--"):
                    if "=" in arg_value:
                        flag_part, _, equals_value = arg_value[2:].partition("=")
                        maybe_flag_delimeter_swapped = "--" + _strings.swap_delimeters(
                            flag_part
                        )
                    else:
                        maybe_flag_delimeter_swapped = "--" + _strings.swap_delimeters(
                            arg_value[2:]
                        )
                else:
                    maybe_flag_delimeter_swapped = arg_value
                    # Also handle short flags with equals, e.g., -f=value.
                    if arg_value.startswith("-") and "=" in arg_value:
                        flag_part, _, equals_value = arg_value.partition("=")
                        maybe_flag_delimeter_swapped = flag_part

                # Helptext.
                if arg_value in ("-h", "--help") and add_help:
                    if console_outputs:
                        print(
                            *_tyro_help_formatting.format_help(
                                prog=local_prog,
                                parser_spec=parser_spec,
                                args=[
                                    arg_ctx_from_dest[arg.get_output_key()]
                                    for arg in itertools.chain(
                                        positional_args, kwarg_map.args()
                                    )
                                ],
                                subparser_frontier=subparser_frontier,
                            ),
                            sep="\n",
                        )
                    sys.exit(0)

                # Handle assignments formatted as --flag=value.
                if equals_value is not None and kwarg_map.contains(
                    maybe_flag_delimeter_swapped
                ):
                    # This should also handle nargs!=1 cases like tuple[int, int].
                    # ["--tuple=1", "2"] will be broken into ["--tuple", "1", "2"].
                    args_deque.appendleft(equals_value)
                    args_deque.appendleft(maybe_flag_delimeter_swapped)
                    continue

                # Check for subparsers in the frontier.
                intern_prefix = None
                for intern_prefix, subparser_spec in subparser_frontier.items():
                    # (1) Backwards compatibility: `None` subcommands were
                    # automatically converted to `none` in tyro<0.10.0.
                    #
                    # (2) For consistency with `--flag-name` and `--flag_name`:
                    # assuming hyphen delimeter, if the actual subcommand is
                    # `subcommand-name`, we support both `subcommand-name` and
                    # `subcommand_name`.
                    #
                    # If the actual subcommand is `subcommand_name` (via manual
                    # override) and the delimeter is `-`, we don't currently
                    # support `subcommand-name`.
                    for arg_value_shim in (
                        (arg_value, _strings.swap_delimeters(arg_value))
                        if not arg_value.endswith("None")
                        else (
                            # This is backwards compatibility shim from before
                            # we supported delimeter swapping in subcommands,
                            # so we can skip the delimeter swap.
                            arg_value,
                            arg_value[:-4] + "none",
                        )
                    ):
                        if (
                            _strings.swap_delimeters(arg_value_shim)
                            in subparser_spec.parser_from_name
                        ):
                            arg_value_shim = _strings.swap_delimeters(arg_value_shim)

                        if arg_value_shim in subparser_spec.parser_from_name:
                            subparser_found = subparser_spec.parser_from_name[
                                arg_value_shim
                            ].evaluate()
                            subparser_found_name = arg_value_shim
                            output[_strings.make_subparser_dest(intern_prefix)] = (
                                arg_value_shim
                            )
                            break
                    if subparser_found is not None:
                        break

                if subparser_found is not None:
                    assert intern_prefix is not None
                    subparser_frontier.pop(intern_prefix)
                    break

                # Handle normal flags.
                short_counter_arg = kwarg_map.get_kwarg(arg_value[:2])
                boolean_value = kwarg_map.get_boolean_value(
                    maybe_flag_delimeter_swapped
                )
                full_arg = kwarg_map.get_kwarg(maybe_flag_delimeter_swapped)
                enforce_mutex_group(short_counter_arg, maybe_flag_delimeter_swapped)
                enforce_mutex_group(full_arg, maybe_flag_delimeter_swapped)
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
                        local_prog,
                        add_help=add_help,
                        console_outputs=console_outputs,
                    )
                    args_to_pop.append(full_arg)
                    continue

                # Implicitly select default subcommands.
                if CascadeSubcommandArgs in parser_spec.markers:
                    # Note: maybe_flag_delimeter_swapped already has the "=value"
                    # part stripped out if present, so we can use it directly.
                    for intern_prefix, subparser in subparser_frontier.items():
                        if (
                            maybe_flag_delimeter_swapped
                            in subparser_implicit_selectors[intern_prefix]
                        ):
                            assert subparser.default_name is not None
                            # Track which subcommand names can't be selected
                            # because of some implicit selection. This will
                            # be used to improve error messages.
                            for parser_name in subparser.parser_from_name.keys():
                                implicit_arg_from_subcommand_name[parser_name] = (
                                    subparser.default_name,
                                    arg_value,
                                )
                            args_deque.appendleft(arg_value)
                            subparser_found = subparser.parser_from_name[
                                subparser.default_name
                            ].evaluate()
                            subparser_found_name = subparser.default_name
                            output[
                                _strings.make_subparser_dest(subparser.intern_prefix)
                            ] = subparser.default_name
                            subparser_frontier.pop(subparser.intern_prefix)
                            break

                    # Done if we found an implicit subcommand.
                    if subparser_found is not None:
                        break

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
                        local_prog,
                        add_help=add_help,
                        console_outputs=console_outputs,
                    )
                    continue

                # If we reach here, we have an unknown argument.
                # Check if this is a subcommand that was implicitly blocked.
                if arg_value in implicit_arg_from_subcommand_name:
                    selected_name, trigger_flag = implicit_arg_from_subcommand_name[
                        arg_value
                    ]
                    if arg_value == selected_name:
                        # Trying to explicitly select the same subcommand that was implicitly selected.
                        _tyro_help_formatting.error_and_exit(
                            "Subcommand already selected",
                            f"The subcommand '{arg_value}' was already implicitly selected when you used the flag '{trigger_flag}'.",
                            "",
                            f"Try removing '{arg_value}' from your command.",
                            prog=local_prog,
                            console_outputs=console_outputs,
                            add_help=add_help,
                        )
                    else:
                        # Trying to select a different subcommand after implicit selection.
                        _tyro_help_formatting.error_and_exit(
                            "Conflicting subcommand selection",
                            f"Cannot select subcommand '{arg_value}' because '{selected_name}'",
                            f"was already implicitly selected when you used the flag '{trigger_flag}'.",
                            "",
                            f"The flag '{trigger_flag}' belongs to the default subcommand",
                            f"'{selected_name}', which implicitly selected it.",
                            "",
                            "Either:",
                            f"  • Remove the conflicting '{trigger_flag}' flag, or",
                            f"  • Move '{arg_value}' earlier in the command",
                            prog=local_prog,
                            console_outputs=console_outputs,
                            add_help=add_help,
                        )
                unknown_args_and_progs.append((arg_value, local_prog))

            # Pop parsed arguments. We de-duplicate using `dest`.
            for arg in {arg.lowered.dest: arg for arg in args_to_pop}.values():
                kwarg_map.pop(arg)

            # Process any missing arguments.
            missing_required_args: list[_tyro_help_formatting.ArgWithContext] = []
            for arg in tuple(positional_args) + tuple(kwarg_map.args()):
                if subparser_found and CascadeSubcommandArgs in arg.field.markers:
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
                elif arg.get_output_key() not in output:
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
                _recurse(subparser_found, prog + " " + subparser_found_name)

        _recurse(parser_spec, prog)

        # Handle any missing/remaining arguments.
        def _check_for_missing_args() -> None:
            missing_required_args: list[_tyro_help_formatting.ArgWithContext] = []
            missing_mutex_groups = set(required_mutex_args.keys()) - set(
                observed_mutex_groups.keys()
            )
            if len(missing_mutex_groups) > 0:
                missing_group_lines = []
                for missing_group in missing_mutex_groups:
                    group_args = required_mutex_args[missing_group]
                    arg_strs = []
                    for arg in group_args:
                        if arg.is_positional():
                            arg_strs.append(f"'{arg.lowered.name_or_flags[-1]}'")
                        else:
                            arg_strs.append(f"{', '.join(arg.lowered.name_or_flags)}")
                    missing_group_lines.append(f"  • {', '.join(arg_strs)}")

                _tyro_help_formatting.error_and_exit(
                    "Required mutex groups"
                    if len(missing_mutex_groups) > 1
                    else "Required mutex group",
                    "Missing required argument groups:"
                    if len(missing_mutex_groups) > 1
                    else "Missing required argument group:",
                    *missing_group_lines,
                    prog=prog,
                    console_outputs=console_outputs,
                    add_help=add_help,
                )
            for arg in itertools.chain(positional_args, kwarg_map.args()):
                if arg.get_output_key() not in output:
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
                subparser_frontier=subparser_frontier,
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
                _recurse(
                    subparser_spec.parser_from_name[
                        subparser_spec.default_name
                    ].evaluate(),
                    local_prog=prog
                    if subparser_spec.prog_suffix == ""
                    else f"{prog} {subparser_spec.prog_suffix}",
                )

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

        This method delegates to ArgparseBackend for backward compatibility
        with code that expects an argparse parser object.
        """
        from ._argparse_backend import ArgparseBackend

        return ArgparseBackend().get_parser_for_completion(
            parser_spec, prog=prog, add_help=add_help
        )

    def generate_completion(
        self,
        parser_spec: _parsers.ParserSpecification,
        prog: str,
        shell: Literal["bash", "zsh", "tcsh"],
        root_prefix: str,
    ) -> str:
        """Generate shell completion script directly from parser specification.

        The TyroBackend provides native completion generation that supports
        tyro-specific features like CascadeSubcommandArgs and frontier-based
        subcommand parsing.

        Args:
            parser_spec: Specification for the parser structure.
            prog: Program name.
            shell: Shell type ('bash' or 'zsh').
            root_prefix: Prefix for completion function names.

        Returns:
            Shell completion script as a string.
        """
        from . import _completion

        if shell == "bash":
            generator = _completion.TyroBashCompletionGenerator()
        elif shell == "zsh":
            generator = _completion.TyroZshCompletionGenerator()
        else:
            raise ValueError(
                f"Unsupported shell '{shell}' for tyro backend completion. "
                f"Supported shells: bash, zsh."
            )

        return generator.generate(parser_spec, prog, root_prefix)
