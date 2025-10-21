"""Custom backend for parsing command-line arguments directly from ParserSpecification.

This backend bypasses argparse entirely and parses arguments directly using the
ParserSpecification. This can be significantly faster for complex command structures
with many subcommands.
"""

from __future__ import annotations

import sys
import warnings
from collections import deque
from typing import Any, Sequence, cast

from .. import _arguments, _parsers, _strings, conf
from . import _help_formatting
from ._argparse_formatter import TyroArgumentParser
from ._base import ParserBackend


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

        self.all_args = args

        out, unknown_args_and_progs = self._parse_args(
            parser_spec,
            args,
            prog,
            return_unknown_args=return_unknown_args,
            console_outputs=console_outputs,
        )
        if unknown_args_and_progs is not None:
            unknown_args = [arg[0] for arg in unknown_args_and_progs]
        else:
            unknown_args = None
        return out, unknown_args

    def _parse_args(
        self,
        parser_spec: _parsers.ParserSpecification,
        args: Sequence[str],
        prog: str,
        return_unknown_args: bool,
        console_outputs: bool,
    ) -> tuple[dict[str | None, Any], list[tuple[str, str]] | None]:
        """Dispatcher that routes to recursive or consolidated parsing."""
        if parser_spec.consolidate_subcommand_args:
            return self._parse_args_consolidated(
                parser_spec, args, prog, return_unknown_args, console_outputs
            )
        else:
            return self._parse_args_recursive(
                parser_spec, args, prog, return_unknown_args, console_outputs
            )

    def _parse_args_recursive(
        self,
        parser_spec: _parsers.ParserSpecification,
        args: Sequence[str],
        prog: str,
        return_unknown_args: bool,
        console_outputs: bool,
        subparser_frontier: dict[str, _parsers.SubparsersSpecification] | None = None,
    ) -> tuple[dict[str | None, Any], list[tuple[str, str]] | None]:
        """Recursive parsing with frontier for normal (non-consolidated) mode."""
        self.args = args
        self.console_outputs = console_outputs

        # Initialize frontier from parser spec if not provided.
        if subparser_frontier is None:
            subparser_frontier = parser_spec.subparsers_from_intern_prefix

        output: dict[str | None, list[str] | bool | str | int | None] = {}

        positional_args: deque[_arguments.ArgumentDefinition] = deque()
        kwarg_from_dest: dict[str, _arguments.ArgumentDefinition] = {}
        dest_from_flag: dict[str, str] = {}
        value_from_boolean_flag: dict[str, bool] = {}
        required_mutex_flags: dict[conf._mutex_group._MutexGroupConfig, list[str]] = {}

        def recurse_children(parser_spec: _parsers.ParserSpecification) -> None:
            # In recursive mode, we include all children arguments.
            # Consolidated mode has its own separate implementation.
            for arg in parser_spec.get_args_including_children():
                if arg.is_suppressed():
                    continue

                mutex_group = arg.field.mutex_group
                if mutex_group is not None and mutex_group.required:
                    if mutex_group not in required_mutex_flags:
                        required_mutex_flags[mutex_group] = []
                    required_mutex_flags[mutex_group].append(
                        arg.lowered.name_or_flags[0]
                    )

                if arg.lowered.action == "append":
                    output[
                        arg.lowered.name_or_flags[-1]
                        if arg.is_positional()
                        else arg.lowered.dest
                    ] = []
                elif arg.lowered.action == "count":
                    output[arg.lowered.dest] = 0

                if arg.is_positional():
                    if len(arg.lowered.name_or_flags) != 1:
                        warnings.warn(
                            f"Positional argument {arg.lowered.name_or_flags} "
                            "should have exactly one name.",
                            category=UserWarning,
                        )
                    positional_args.append(arg)
                else:
                    assert arg.lowered.dest is not None
                    kwarg_from_dest[arg.lowered.dest] = arg

                    # Map flags to their destination.
                    for name in arg.lowered.name_or_flags:
                        assert name not in dest_from_flag, f"Duplicate flag: {name}"
                        dest_from_flag[name] = arg.lowered.dest

                        # Handle boolean flags.
                        if arg.lowered.action == "store_true":
                            value_from_boolean_flag[name] = True
                        elif arg.lowered.action == "store_false":
                            value_from_boolean_flag[name] = False
                        elif arg.lowered.action == "boolean_optional_action":
                            inv_name = _arguments.flag_to_inverse(name)
                            assert inv_name not in dest_from_flag, (
                                f"Duplicate flag: {inv_name}"
                            )
                            dest_from_flag[inv_name] = arg.lowered.dest
                            value_from_boolean_flag[name] = True
                            value_from_boolean_flag[
                                _arguments.flag_to_inverse(name)
                            ] = False

        recurse_children(parser_spec)

        # Add help flag to dest_from_flag. This is used for "is valid flag" checks.
        if parser_spec.add_help:
            dest_from_flag["-h"] = "__help__"
            dest_from_flag["--help"] = "__help__"

        # Helpers for enforcing mutex groups.
        observed_mutex_groups: dict[conf._mutex_group._MutexGroupConfig, str] = {}

        def enforce_mutex_group(
            arg: _arguments.ArgumentDefinition, actual_arg: str
        ) -> None:
            if arg.field.mutex_group is None:
                return
            existing_arg = observed_mutex_groups.get(arg.field.mutex_group, None)
            if existing_arg is not None:
                _help_formatting.error_and_exit(
                    "Mutually exclusive arguments",
                    f"Arguments {existing_arg} and {actual_arg} are not allowed together!",
                    prog=prog,
                    console_outputs=console_outputs,
                    add_help=parser_spec.add_help,
                )
            observed_mutex_groups[arg.field.mutex_group] = actual_arg

        # We'll consume arguments from left-to-right.
        args_deque = deque(args)
        unknown_args_and_progs: list[tuple[str, str]] = []
        subparser_found: bool = False
        while len(args_deque) > 0:
            arg_value_peek = args_deque[0]

            # Handle keyword arguments.
            if (
                # Cases like -vvv.
                arg_value_peek[:2] in dest_from_flag
                and kwarg_from_dest[dest_from_flag[arg_value_peek[:2]]].lowered.action
                == "count"
                and arg_value_peek
                == arg_value_peek[:2] + (len(arg_value_peek) - 2) * arg_value_peek[1]
            ):
                args_deque.popleft()
                dest = dest_from_flag[arg_value_peek[:2]]
                output[dest] = cast(int, output[dest]) + len(arg_value_peek) - 1
                continue
            elif arg_value_peek in dest_from_flag:
                if parser_spec.add_help and arg_value_peek in ("-h", "--help"):
                    # Help flag.
                    if console_outputs:
                        print(
                            *_help_formatting.format_help(
                                prog=prog if prog is not None else sys.argv[0],
                                parser_specs=[parser_spec],
                                subparser_frontier=subparser_frontier,
                            ),
                            sep="\n",
                        )
                    sys.exit(0)
                elif arg_value_peek in value_from_boolean_flag:
                    # --flag or --no-flag.
                    args_deque.popleft()
                    arg = kwarg_from_dest[dest_from_flag[arg_value_peek]]
                    enforce_mutex_group(arg, arg_value_peek)
                    output[arg.lowered.dest] = value_from_boolean_flag[arg_value_peek]
                    continue
                elif (
                    kwarg_from_dest[dest_from_flag[arg_value_peek]].lowered.action
                    == "count"
                ):
                    # Cases like -v -v -v, or --verbose --verbose.
                    args_deque.popleft()
                    dest = dest_from_flag[arg_value_peek]
                    output[dest] = cast(int, output[dest]) + 1
                    continue
                else:
                    # Standard kwarg.
                    args_deque.popleft()
                    arg = kwarg_from_dest[dest_from_flag[arg_value_peek]]
                    enforce_mutex_group(arg, arg_value_peek)
                    dest = arg.lowered.dest
                    arg_values = self._consume_argument(
                        arg,
                        args_deque,
                        dest_from_flag,
                        subparser_frontier,
                        prog,
                        add_help=parser_spec.add_help,
                    )
                    if arg.lowered.action == "append":
                        cast(list, output[dest]).append(arg_values)
                    elif arg.lowered.nargs == "?" and len(arg_values) == 1:
                        # Special case for nargs="?"; this is matched in _calling.py.
                        output[dest] = arg_values[0]
                    else:
                        output[dest] = arg_values
                    continue

            # Handle cases like --flag=value.
            if arg_value_peek.startswith("-") and "=" in arg_value_peek:
                maybe_flag, _, value = arg_value_peek.partition("=")
                if maybe_flag in dest_from_flag:
                    # This should also handle nargs!=1 cases like tuple[int, int].
                    # ["--tuple=1", "2"] will be broken into ["--tuple", "1", "2"].
                    args_deque.popleft()
                    args_deque.appendleft(value)
                    args_deque.appendleft(maybe_flag)
                    continue

            # Check for subparsers in frontier.
            subparser_found = False
            for intern_prefix, subparser_spec in subparser_frontier.items():
                if arg_value_peek in subparser_spec.parser_from_name:
                    args_deque.popleft()
                    output[_strings.make_subparser_dest(intern_prefix)] = arg_value_peek

                    # Build new frontier: remove this group, add child's groups.
                    chosen_parser = subparser_spec.parser_from_name[arg_value_peek]
                    new_frontier = {
                        k: v
                        for k, v in subparser_frontier.items()
                        if k != intern_prefix
                    }
                    new_frontier |= chosen_parser.subparsers_from_intern_prefix

                    # Recurse into child parser with updated frontier.
                    inner_output, inner_unknown_args = self._parse_args_recursive(
                        chosen_parser,
                        args_deque,
                        prog=prog + " " + arg_value_peek,
                        return_unknown_args=True,
                        console_outputs=console_outputs,
                        subparser_frontier=new_frontier,
                    )
                    assert inner_unknown_args is not None
                    output.update(inner_output)
                    unknown_args_and_progs.extend(inner_unknown_args)
                    subparser_found = True
                    break

            if subparser_found:
                break

            # Handle positional arguments.
            if len(positional_args) > 0:
                arg = positional_args.popleft()
                assert arg.lowered.dest is None
                dest = arg.lowered.name_or_flags[-1]
                arg_values = self._consume_argument(
                    arg,
                    args_deque,
                    dest_from_flag,
                    subparser_frontier,
                    prog,
                    add_help=parser_spec.add_help,
                )
                if arg.lowered.action == "append":
                    cast(list, output[dest]).append(arg_values)
                elif arg.lowered.nargs == "?" and len(arg_values) == 1:
                    # Special case for nargs="?"; this is matched in _calling.py.
                    output[dest] = arg_values[0]
                else:
                    output[dest] = arg_values
                continue

            # If we reach here, we have an unknown argument.
            unknown_args_and_progs.append((args_deque.popleft(), prog))

        # Found unknown arguments.
        if not return_unknown_args and len(unknown_args_and_progs) > 0:
            _help_formatting.unrecognized_args_error(
                prog=prog,
                unrecognized_args_and_progs=unknown_args_and_progs,
                args=list(self.all_args),
                parser_spec=parser_spec,
                console_outputs=self.console_outputs,
            )

        # Handle default subcommands for frontier groups.
        for intern_prefix, subparser_spec in subparser_frontier.items():
            dest = _strings.make_subparser_dest(intern_prefix)
            if dest not in output:
                # No subcommand was selected for this group.
                default_subcommand = subparser_spec.default_name
                if default_subcommand is None:
                    # No default available; this is an error.
                    _help_formatting.error_and_exit(
                        "Missing subcommand",
                        f"Expected subcommand from {list(subparser_spec.parser_from_name.keys())}, "
                        f"but found: {args_deque[0] if len(args_deque) > 0 else 'nothing'}.",
                        prog=prog,
                        console_outputs=console_outputs,
                        add_help=parser_spec.add_help,
                    )
                else:
                    # Use the default subcommand.
                    output[dest] = default_subcommand

                    # Build new frontier: remove this group, add child's groups.
                    chosen_parser = subparser_spec.parser_from_name[default_subcommand]
                    new_frontier = {
                        k: v
                        for k, v in subparser_frontier.items()
                        if k != intern_prefix
                    }
                    new_frontier |= chosen_parser.subparsers_from_intern_prefix

                    # Recurse with updated frontier and empty args.
                    inner_output, inner_unknown_args = self._parse_args_recursive(
                        chosen_parser,
                        [],
                        prog=prog + " " + default_subcommand,
                        return_unknown_args=False,
                        console_outputs=console_outputs,
                        subparser_frontier=new_frontier,
                    )
                    output.update(inner_output)
                    del inner_unknown_args

        # Go through remaining keyword arguments.
        missing_required_args: list[str] = []

        missing_mutex_groups = set(required_mutex_flags.keys()) - set(
            observed_mutex_groups.keys()
        )
        for missing_group in missing_mutex_groups:
            missing_required_args.append(
                "{" + ",".join(required_mutex_flags[missing_group]) + "}"
            )

        for dest, arg in kwarg_from_dest.items():
            # Argument was passed in.
            if dest in output:
                continue

            # Argument is required.
            if arg.lowered.required is True:
                missing_required_args.append(arg.lowered.name_or_flags[-1])

            # Argument is optional: we'll use the default value in _calling.py.
            output[dest] = arg.lowered.default
        if len(missing_required_args) > 0:
            _help_formatting.required_args_error(
                prog=prog,
                required_args=missing_required_args,
                args=list(self.all_args),
                parser_spec=parser_spec,
                console_outputs=self.console_outputs,
            )

        for arg in positional_args:
            if arg.lowered.name_or_flags[-1] in output:
                continue
            output[arg.lowered.name_or_flags[-1]] = arg.lowered.default

        return output, unknown_args_and_progs if return_unknown_args else None

    def _parse_args_consolidated(
        self,
        parser_spec: _parsers.ParserSpecification,
        args: Sequence[str],
        prog: str,
        return_unknown_args: bool,
        console_outputs: bool,
    ) -> tuple[dict[str | None, Any], list[tuple[str, str]] | None]:
        """Iterative parsing with frontier for consolidated mode.

        In consolidated mode, arguments from child parsers are dynamically added
        to the current parsing context as subcommands are selected. Multiple
        frontier groups can be interleaved in the same command line.
        """
        self.args = args
        self.console_outputs = console_outputs

        # Initialize frontier from parser spec.
        subparser_frontier = parser_spec.subparsers_from_intern_prefix.copy()

        output: dict[str | None, list[str] | bool | str | int | None] = {}

        positional_args: deque[_arguments.ArgumentDefinition] = deque()
        kwarg_from_dest: dict[str, _arguments.ArgumentDefinition] = {}
        dest_from_flag: dict[str, str] = {}
        value_from_boolean_flag: dict[str, bool] = {}
        required_mutex_flags: dict[conf._mutex_group._MutexGroupConfig, list[str]] = {}

        def add_parser_args(parser_spec: _parsers.ParserSpecification) -> None:
            # Add arguments from this parser (including nested fields, but not subparsers).
            for arg in parser_spec.get_args_including_children():
                if arg.is_suppressed():
                    continue

                mutex_group = arg.field.mutex_group
                if mutex_group is not None and mutex_group.required:
                    if mutex_group not in required_mutex_flags:
                        required_mutex_flags[mutex_group] = []
                    required_mutex_flags[mutex_group].append(
                        arg.lowered.name_or_flags[0]
                    )

                if arg.lowered.action == "append":
                    output[
                        arg.lowered.name_or_flags[-1]
                        if arg.is_positional()
                        else arg.lowered.dest
                    ] = []
                elif arg.lowered.action == "count":
                    output[arg.lowered.dest] = 0

                if arg.is_positional():
                    if len(arg.lowered.name_or_flags) != 1:
                        warnings.warn(
                            f"Positional argument {arg.lowered.name_or_flags} "
                            "should have exactly one name.",
                            category=UserWarning,
                        )
                    positional_args.append(arg)
                else:
                    assert arg.lowered.dest is not None
                    kwarg_from_dest[arg.lowered.dest] = arg

                    # Map flags to their destination.
                    for name in arg.lowered.name_or_flags:
                        assert name not in dest_from_flag, f"Duplicate flag: {name}"
                        dest_from_flag[name] = arg.lowered.dest

                        # Handle boolean flags.
                        if arg.lowered.action == "store_true":
                            value_from_boolean_flag[name] = True
                        elif arg.lowered.action == "store_false":
                            value_from_boolean_flag[name] = False
                        elif arg.lowered.action == "boolean_optional_action":
                            inv_name = _arguments.flag_to_inverse(name)
                            assert inv_name not in dest_from_flag, (
                                f"Duplicate flag: {inv_name}"
                            )
                            dest_from_flag[inv_name] = arg.lowered.dest
                            value_from_boolean_flag[name] = True
                            value_from_boolean_flag[
                                _arguments.flag_to_inverse(name)
                            ] = False

        # Add root parser's arguments including nested fields.
        # Note: get_args_including_children() includes nested dataclass fields
        # but NOT subparser choices, so this is safe.
        for arg in parser_spec.get_args_including_children():
            if arg.is_suppressed():
                continue

            mutex_group = arg.field.mutex_group
            if mutex_group is not None and mutex_group.required:
                if mutex_group not in required_mutex_flags:
                    required_mutex_flags[mutex_group] = []
                required_mutex_flags[mutex_group].append(arg.lowered.name_or_flags[0])

            if arg.lowered.action == "append":
                output[
                    arg.lowered.name_or_flags[-1]
                    if arg.is_positional()
                    else arg.lowered.dest
                ] = []
            elif arg.lowered.action == "count":
                output[arg.lowered.dest] = 0

            if arg.is_positional():
                if len(arg.lowered.name_or_flags) != 1:
                    warnings.warn(
                        f"Positional argument {arg.lowered.name_or_flags} "
                        "should have exactly one name.",
                        category=UserWarning,
                    )
                positional_args.append(arg)
            else:
                assert arg.lowered.dest is not None
                kwarg_from_dest[arg.lowered.dest] = arg

                # Map flags to their destination.
                for name in arg.lowered.name_or_flags:
                    assert name not in dest_from_flag, f"Duplicate flag: {name}"
                    dest_from_flag[name] = arg.lowered.dest

                    # Handle boolean flags.
                    if arg.lowered.action == "store_true":
                        value_from_boolean_flag[name] = True
                    elif arg.lowered.action == "store_false":
                        value_from_boolean_flag[name] = False
                    elif arg.lowered.action == "boolean_optional_action":
                        inv_name = _arguments.flag_to_inverse(name)
                        assert inv_name not in dest_from_flag, (
                            f"Duplicate flag: {inv_name}"
                        )
                        dest_from_flag[inv_name] = arg.lowered.dest
                        value_from_boolean_flag[name] = True
                        value_from_boolean_flag[_arguments.flag_to_inverse(name)] = (
                            False
                        )

        # Add parent's arguments if applicable (for nested consolidation).
        if parser_spec.subparser_parent is not None:
            add_parser_args(parser_spec.subparser_parent)

        # Add help flag to dest_from_flag.
        if parser_spec.add_help:
            dest_from_flag["-h"] = "__help__"
            dest_from_flag["--help"] = "__help__"

        # Phase 1: Gather all activated parsers by scanning for subcommands.
        def gather_activated_parsers(
            current_frontier: dict[str, _parsers.SubparsersSpecification],
            subcommand_selections: dict[str, str],
            consumed_args: set[int],
        ) -> list[_parsers.ParserSpecification]:
            """Recursively find all parsers activated by subcommand selections."""
            activated = []

            for idx, arg in enumerate(args):
                if idx in consumed_args:
                    continue
                for intern_prefix, subparser_spec in current_frontier.items():
                    if arg in subparser_spec.parser_from_name:
                        # Record the selection.
                        subcommand_selections[intern_prefix] = arg
                        consumed_args.add(idx)
                        chosen_parser = subparser_spec.parser_from_name[arg]
                        activated.append(chosen_parser)

                        # Build new frontier and recurse.
                        new_frontier = {
                            k: v
                            for k, v in current_frontier.items()
                            if k != intern_prefix
                        }
                        new_frontier |= chosen_parser.subparsers_from_intern_prefix

                        activated.extend(
                            gather_activated_parsers(
                                new_frontier, subcommand_selections, consumed_args
                            )
                        )
                        break

            return activated

        # Gather all activated parsers.
        subcommand_selections: dict[str, str] = {}
        consumed_args: set[int] = set()
        activated_parsers = gather_activated_parsers(
            subparser_frontier, subcommand_selections, consumed_args
        )

        # Record subcommand selections in output.
        for intern_prefix, subcommand_name in subcommand_selections.items():
            output[_strings.make_subparser_dest(intern_prefix)] = subcommand_name

        # Phase 2: Merge arguments from all activated parsers.
        for activated_parser in activated_parsers:
            add_parser_args(activated_parser)

        # Handle defaults for unselected frontier groups.
        for intern_prefix, subparser_spec in subparser_frontier.items():
            dest = _strings.make_subparser_dest(intern_prefix)
            if dest not in output:
                default_subcommand = subparser_spec.default_name
                if default_subcommand is None:
                    # No subcommand selected and no default; error.
                    _help_formatting.error_and_exit(
                        "Missing subcommand",
                        f"Expected subcommand from {list(subparser_spec.parser_from_name.keys())}, "
                        f"but none was provided.",
                        prog=prog,
                        console_outputs=console_outputs,
                        add_help=parser_spec.add_help,
                    )
                else:
                    # Use default and activate its parser.
                    output[dest] = default_subcommand
                    default_parser = subparser_spec.parser_from_name[default_subcommand]
                    add_parser_args(default_parser)

        # Helpers for enforcing mutex groups.
        observed_mutex_groups: dict[conf._mutex_group._MutexGroupConfig, str] = {}

        def enforce_mutex_group(
            arg: _arguments.ArgumentDefinition, actual_arg: str
        ) -> None:
            if arg.field.mutex_group is None:
                return
            existing_arg = observed_mutex_groups.get(arg.field.mutex_group, None)
            if existing_arg is not None:
                _help_formatting.error_and_exit(
                    "Mutually exclusive arguments",
                    f"Arguments {existing_arg} and {actual_arg} are not allowed together!",
                    prog=prog,
                    console_outputs=console_outputs,
                    add_help=parser_spec.add_help,
                )
            observed_mutex_groups[arg.field.mutex_group] = actual_arg

        # Phase 3: Parse arguments with merged argument set.
        args_deque = deque(args)
        unknown_args_and_progs: list[tuple[str, str]] = []

        while len(args_deque) > 0:
            arg_value_peek = args_deque[0]

            # Handle keyword arguments.
            if (
                arg_value_peek[:2] in dest_from_flag
                and kwarg_from_dest[dest_from_flag[arg_value_peek[:2]]].lowered.action
                == "count"
                and arg_value_peek
                == arg_value_peek[:2] + (len(arg_value_peek) - 2) * arg_value_peek[1]
            ):
                # Cases like -vvv.
                args_deque.popleft()
                dest = dest_from_flag[arg_value_peek[:2]]
                output[dest] = cast(int, output[dest]) + len(arg_value_peek) - 1
                continue
            elif arg_value_peek in dest_from_flag:
                if parser_spec.add_help and arg_value_peek in ("-h", "--help"):
                    # Help flag. In consolidated mode, show help including activated parsers
                    # up to this point (scan only what we've seen so far).
                    if console_outputs:
                        # Gather activated parsers based on subcommands seen before --help.
                        # Use args consumed so far (original args minus remaining deque).
                        args_before_help = args[: len(args) - len(args_deque)]
                        subcommand_selections: dict[str, str] = {}
                        consumed_args: set[int] = set()

                        # Redefine gather function to scan only args before help.
                        def gather_for_help(
                            current_frontier: dict[
                                str, _parsers.SubparsersSpecification
                            ],
                            subcommand_selections: dict[str, str],
                            consumed_args: set[int],
                        ) -> list[_parsers.ParserSpecification]:
                            activated = []
                            for idx, arg in enumerate(args_before_help):
                                if idx in consumed_args:
                                    continue
                                for (
                                    intern_prefix,
                                    subparser_spec,
                                ) in current_frontier.items():
                                    if arg in subparser_spec.parser_from_name:
                                        subcommand_selections[intern_prefix] = arg
                                        consumed_args.add(idx)
                                        chosen_parser = subparser_spec.parser_from_name[
                                            arg
                                        ]
                                        activated.append(chosen_parser)
                                        new_frontier = {
                                            k: v
                                            for k, v in current_frontier.items()
                                            if k != intern_prefix
                                        }
                                        new_frontier |= (
                                            chosen_parser.subparsers_from_intern_prefix
                                        )
                                        activated.extend(
                                            gather_for_help(
                                                new_frontier,
                                                subcommand_selections,
                                                consumed_args,
                                            )
                                        )
                                        break
                            return activated

                        activated_parsers = gather_for_help(
                            subparser_frontier, subcommand_selections, consumed_args
                        )

                        # Build the updated frontier after activations.
                        help_frontier = dict(subparser_frontier)
                        for intern_prefix in subcommand_selections:
                            del help_frontier[intern_prefix]
                        for parser in activated_parsers:
                            help_frontier |= parser.subparsers_from_intern_prefix

                        # Build prog string including selected subcommands.
                        help_prog = prog if prog is not None else sys.argv[0]
                        for subcommand_name in subcommand_selections.values():
                            help_prog += " " + subcommand_name

                        # Show help with root + activated parsers.
                        print(
                            *_help_formatting.format_help(
                                prog=help_prog,
                                parser_specs=[parser_spec] + activated_parsers,
                                subparser_frontier=help_frontier,
                            ),
                            sep="\n",
                        )
                    sys.exit(0)
                elif arg_value_peek in value_from_boolean_flag:
                    # --flag or --no-flag.
                    args_deque.popleft()
                    arg = kwarg_from_dest[dest_from_flag[arg_value_peek]]
                    enforce_mutex_group(arg, arg_value_peek)
                    output[arg.lowered.dest] = value_from_boolean_flag[arg_value_peek]
                    continue
                elif (
                    kwarg_from_dest[dest_from_flag[arg_value_peek]].lowered.action
                    == "count"
                ):
                    # Cases like -v -v -v.
                    args_deque.popleft()
                    dest = dest_from_flag[arg_value_peek]
                    output[dest] = cast(int, output[dest]) + 1
                    continue
                else:
                    # Standard kwarg.
                    args_deque.popleft()
                    arg = kwarg_from_dest[dest_from_flag[arg_value_peek]]
                    enforce_mutex_group(arg, arg_value_peek)
                    dest = arg.lowered.dest
                    arg_values = self._consume_argument(
                        arg,
                        args_deque,
                        dest_from_flag,
                        subparser_frontier,
                        prog,
                        add_help=parser_spec.add_help,
                    )
                    if arg.lowered.action == "append":
                        cast(list, output[dest]).append(arg_values)
                    elif arg.lowered.nargs == "?" and len(arg_values) == 1:
                        output[dest] = arg_values[0]
                    else:
                        output[dest] = arg_values
                    continue

            # Handle --flag=value.
            if arg_value_peek.startswith("-") and "=" in arg_value_peek:
                maybe_flag, _, value = arg_value_peek.partition("=")
                if maybe_flag in dest_from_flag:
                    args_deque.popleft()
                    args_deque.appendleft(value)
                    args_deque.appendleft(maybe_flag)
                    continue

            # Skip subcommand tokens (already processed).
            if any(
                arg_value_peek in spec.parser_from_name
                for spec in subparser_frontier.values()
            ):
                args_deque.popleft()
                continue

            # Handle positional arguments.
            if len(positional_args) > 0:
                arg = positional_args.popleft()
                assert arg.lowered.dest is None
                dest = arg.lowered.name_or_flags[-1]
                arg_values = self._consume_argument(
                    arg,
                    args_deque,
                    dest_from_flag,
                    subparser_frontier,
                    prog,
                    add_help=parser_spec.add_help,
                )
                if arg.lowered.action == "append":
                    cast(list, output[dest]).append(arg_values)
                elif arg.lowered.nargs == "?" and len(arg_values) == 1:
                    output[dest] = arg_values[0]
                else:
                    output[dest] = arg_values
                continue

            # Unknown argument.
            unknown_args_and_progs.append((args_deque.popleft(), prog))

        # Error on unknown arguments.
        if not return_unknown_args and len(unknown_args_and_progs) > 0:
            _help_formatting.unrecognized_args_error(
                prog=prog,
                unrecognized_args_and_progs=unknown_args_and_progs,
                args=list(self.all_args),
                parser_spec=parser_spec,
                console_outputs=self.console_outputs,
            )

        # Check for missing required arguments.
        missing_required_args: list[str] = []

        missing_mutex_groups = set(required_mutex_flags.keys()) - set(
            observed_mutex_groups.keys()
        )
        for missing_group in missing_mutex_groups:
            missing_required_args.append("/".join(required_mutex_flags[missing_group]))

        for dest, arg in kwarg_from_dest.items():
            if arg.lowered.required and dest not in output:
                missing_required_args.append(arg.lowered.name_or_flags[0])

        if len(missing_required_args) > 0:
            _help_formatting.error_and_exit(
                "Missing required arguments",
                f"Required: {', '.join(missing_required_args)}",
                prog=prog,
                console_outputs=console_outputs,
                add_help=parser_spec.add_help,
            )

        # Set defaults for unset positional arguments.
        for arg in positional_args:
            if arg.lowered.name_or_flags[-1] in output:
                continue
            output[arg.lowered.name_or_flags[-1]] = arg.lowered.default

        return output, unknown_args_and_progs if return_unknown_args else None

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

    def _consume_argument(
        self,
        arg: _arguments.ArgumentDefinition,
        args_deque: deque[str],
        dest_from_flag: dict[str, str],
        subparser_frontier: dict[str, _parsers.SubparsersSpecification],
        prog: str,
        add_help: bool,
    ) -> list[str]:
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
                        console_outputs=self.console_outputs,
                        add_help=add_help,
                    )
                arg_values.append(args_deque.popleft())
        elif arg.lowered.nargs in ("+", "*", "?"):
            counter = 0
            while (
                len(args_deque) > 0
                and args_deque[0] not in dest_from_flag
                # To match argparse behavior:
                # - When nargs are present, we assume any `--` flag is a valid argument.
                and not args_deque[0].startswith("--")
                and (arg.lowered.nargs != "?" or counter == 0)
                and (
                    # Break if we reach a subparser. This diverges from
                    # argparse's behavior slightly, which has tradeoffs...
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
                    console_outputs=self.console_outputs,
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
                        console_outputs=self.console_outputs,
                        add_help=add_help,
                    )

        return arg_values
