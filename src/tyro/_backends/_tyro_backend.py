"""Custom backend for parsing command-line arguments directly from ParserSpecification.

This backend bypasses argparse entirely and parses arguments directly using the
ParserSpecification. This can be significantly faster for complex command structures
with many subcommands.
"""

from __future__ import annotations

import sys
import warnings
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Sequence, cast

from .. import _arguments, _parsers, _strings, conf
from . import _help_formatting
from ._argparse_formatter import TyroArgumentParser
from ._base import ParserBackend


@dataclass
class ArgumentMaps:
    """Maps for looking up argument definitions and their properties."""

    positional_args: deque[_arguments.ArgumentDefinition] = field(default_factory=deque)
    kwarg_from_dest: dict[str, _arguments.ArgumentDefinition] = field(
        default_factory=dict
    )
    dest_from_flag: dict[str, str] = field(default_factory=dict)
    value_from_boolean_flag: dict[str, bool] = field(default_factory=dict)
    required_mutex_flags: dict[conf._mutex_group._MutexGroupConfig, list[str]] = field(
        default_factory=dict
    )


@dataclass
class ParsingState:
    """State maintained during argument parsing."""

    # Accumulated output values.
    # Keys are dest strings (for kwargs) or argument names (for positionals).
    # Values can be: bool (boolean flags), int (count actions), str (single value),
    # list[str] (multiple values or nargs), or Any (default values).
    output: dict[str | None, Any] = field(default_factory=dict)

    # Mutex groups that have been used, mapping to the flag that was used.
    observed_mutex_groups: dict[conf._mutex_group._MutexGroupConfig, str] = field(
        default_factory=dict
    )

    # Unknown arguments paired with their prog context for error reporting.
    unknown_args_and_progs: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class ParsingContext:
    """Encapsulates all state and logic for parsing command-line arguments.

    This class handles the shared parsing logic between recursive and consolidated
    modes. The main difference between modes is when arguments are registered and
    how subcommands are handled.
    """

    parser_spec: _parsers.ParserSpecification
    args: Sequence[str]
    prog: str
    console_outputs: bool
    full_args: Sequence[str] | None = None  # Full argument list for error messages.
    root_parser_spec: _parsers.ParserSpecification | None = (
        None  # Root parser for error messages.
    )

    # Parsing state.
    maps: ArgumentMaps = field(default_factory=ArgumentMaps)
    state: ParsingState = field(default_factory=ParsingState)

    def __post_init__(self):
        """Initialize full_args and root_parser_spec if not provided."""
        if self.full_args is None:
            self.full_args = self.args
        if self.root_parser_spec is None:
            self.root_parser_spec = self.parser_spec

    def register_argument(self, arg: _arguments.ArgumentDefinition) -> None:
        """Register a single argument definition into the parsing maps.

        Args:
            arg: The argument definition to register.
        """
        if arg.is_suppressed():
            return

        # Track required mutex groups.
        mutex_group = arg.field.mutex_group
        if mutex_group is not None and mutex_group.required:
            if mutex_group not in self.maps.required_mutex_flags:
                self.maps.required_mutex_flags[mutex_group] = []
            self.maps.required_mutex_flags[mutex_group].append(
                arg.lowered.name_or_flags[0]
            )

        # Initialize output for append/count actions.
        if arg.lowered.action == "append":
            dest_or_name = (
                arg.lowered.name_or_flags[-1]
                if arg.is_positional()
                else arg.lowered.dest
            )
            self.state.output[dest_or_name] = []
        elif arg.lowered.action == "count":
            self.state.output[arg.lowered.dest] = 0

        # Handle positional vs keyword arguments.
        if arg.is_positional():
            if len(arg.lowered.name_or_flags) != 1:
                warnings.warn(
                    f"Positional argument {arg.lowered.name_or_flags} "
                    "should have exactly one name.",
                    category=UserWarning,
                )
            self.maps.positional_args.append(arg)
        else:
            assert arg.lowered.dest is not None
            self.maps.kwarg_from_dest[arg.lowered.dest] = arg

            # Map all flags to their destination.
            self._register_flags(arg)

    def _register_flags(self, arg: _arguments.ArgumentDefinition) -> None:
        """Register flag mappings for a keyword argument.

        Args:
            arg: The keyword argument definition.
        """
        assert arg.lowered.dest is not None

        for name in arg.lowered.name_or_flags:
            assert name not in self.maps.dest_from_flag, f"Duplicate flag: {name}"
            self.maps.dest_from_flag[name] = arg.lowered.dest

            # Handle boolean flags.
            if arg.lowered.action == "store_true":
                self.maps.value_from_boolean_flag[name] = True
            elif arg.lowered.action == "store_false":
                self.maps.value_from_boolean_flag[name] = False
            elif arg.lowered.action == "boolean_optional_action":
                inv_name = _arguments.flag_to_inverse(name)
                assert inv_name not in self.maps.dest_from_flag, (
                    f"Duplicate flag: {inv_name}"
                )
                self.maps.dest_from_flag[inv_name] = arg.lowered.dest
                self.maps.value_from_boolean_flag[name] = True
                self.maps.value_from_boolean_flag[inv_name] = False

    def register_parser_args(
        self,
        parser_spec: _parsers.ParserSpecification,
    ) -> None:
        """Register all arguments from a parser specification.

        Args:
            parser_spec: The parser specification to register arguments from.
        """
        for arg in parser_spec.get_args_including_children():
            self.register_argument(arg)

    def add_help_flags(self) -> None:
        """Add help flags to the destination mapping."""
        if self.parser_spec.add_help:
            self.maps.dest_from_flag["-h"] = "__help__"
            self.maps.dest_from_flag["--help"] = "__help__"

    def enforce_mutex_group(
        self,
        arg: _arguments.ArgumentDefinition,
        actual_arg: str,
    ) -> None:
        """Enforce mutually exclusive argument constraints.

        Args:
            arg: The argument definition being parsed.
            actual_arg: The actual flag string used (for error messages).

        Raises:
            SystemExit: If mutex constraint is violated.
        """
        if arg.field.mutex_group is None:
            return

        existing_arg = self.state.observed_mutex_groups.get(arg.field.mutex_group)
        if existing_arg is not None:
            _help_formatting.error_and_exit(
                "Mutually exclusive arguments",
                f"Arguments {existing_arg} and {actual_arg} are not allowed together!",
                prog=self.prog,
                console_outputs=self.console_outputs,
                add_help=self.parser_spec.add_help,
            )

        self.state.observed_mutex_groups[arg.field.mutex_group] = actual_arg

    def try_parse_count_flag(self, arg_value: str, args_deque: deque[str]) -> bool:
        """Try to parse a count flag like -vvv.

        Args:
            arg_value: The current argument value.
            args_deque: Remaining arguments to consume from.

        Returns:
            True if the argument was a count flag and was parsed.
        """
        # Check for patterns like -vvv (short flag repeated).
        if (
            len(arg_value) >= 2
            and arg_value[:2] in self.maps.dest_from_flag
            and arg_value == arg_value[:2] + (len(arg_value) - 2) * arg_value[1]
        ):
            dest = self.maps.dest_from_flag[arg_value[:2]]
            if dest in self.maps.kwarg_from_dest:
                arg = self.maps.kwarg_from_dest[dest]
                if arg.lowered.action == "count":
                    args_deque.popleft()
                    self.state.output[dest] = (
                        cast(int, self.state.output[dest]) + len(arg_value) - 1
                    )
                    return True
        return False

    def try_parse_keyword_arg(
        self,
        arg_value: str,
        args_deque: deque[str],
        subparser_frontier: dict[str, _parsers.SubparsersSpecification],
    ) -> bool:
        """Try to parse a keyword argument.

        Args:
            arg_value: The current argument value.
            args_deque: Remaining arguments to consume from.
            subparser_frontier: Current subparser frontier for help context.

        Returns:
            True if the argument was a keyword argument and was parsed.
        """
        if arg_value not in self.maps.dest_from_flag:
            return False

        # Handle help flag.
        if self.parser_spec.add_help and arg_value in ("-h", "--help"):
            self._show_help(subparser_frontier)
            sys.exit(0)

        args_deque.popleft()
        dest = self.maps.dest_from_flag[arg_value]
        arg = self.maps.kwarg_from_dest[dest]

        # Handle boolean flags.
        if arg_value in self.maps.value_from_boolean_flag:
            self.enforce_mutex_group(arg, arg_value)
            self.state.output[dest] = self.maps.value_from_boolean_flag[arg_value]
            return True

        # Handle count flags.
        if arg.lowered.action == "count":
            self.state.output[dest] = cast(int, self.state.output[dest]) + 1
            return True

        # Handle standard keyword arguments.
        self.enforce_mutex_group(arg, arg_value)
        arg_values = self._consume_argument(
            arg,
            args_deque,
            subparser_frontier,
        )

        if arg.lowered.action == "append":
            cast(list, self.state.output[dest]).append(arg_values)
        elif arg.lowered.nargs == "?" and len(arg_values) == 1:  # pragma: no cover
            # TODO: only used for positional args.
            self.state.output[dest] = arg_values[0]
        else:
            self.state.output[dest] = arg_values

        return True

    def try_parse_flag_equals_value(
        self,
        arg_value: str,
        args_deque: deque[str],
    ) -> bool:
        """Try to parse --flag=value syntax.

        Args:
            arg_value: The current argument value.
            args_deque: Remaining arguments to consume from.

        Returns:
            True if the argument was in --flag=value format and was split.
        """
        if not (arg_value.startswith("-") and "=" in arg_value):
            return False

        maybe_flag, _, value = arg_value.partition("=")
        if maybe_flag in self.maps.dest_from_flag:
            # Split into ["--flag", "value"] for standard processing.
            args_deque.popleft()
            args_deque.appendleft(value)
            args_deque.appendleft(maybe_flag)
            return True

        return False

    def try_parse_positional_arg(
        self,
        args_deque: deque[str],
        subparser_frontier: dict[str, _parsers.SubparsersSpecification],
    ) -> bool:
        """Try to parse a positional argument.

        Args:
            args_deque: Remaining arguments to consume from.
            subparser_frontier: Current subparser frontier.

        Returns:
            True if a positional argument was parsed.
        """
        if len(self.maps.positional_args) == 0:
            return False

        arg = self.maps.positional_args.popleft()
        assert arg.lowered.dest is None
        dest = arg.lowered.name_or_flags[-1]

        arg_values = self._consume_argument(arg, args_deque, subparser_frontier)

        if arg.lowered.action == "append":  #  pragma: no cover
            # TODO: not possible for positional? This and above could use consolidation.
            cast(list, self.state.output[dest]).append(arg_values)
        elif arg.lowered.nargs == "?" and len(arg_values) == 1:
            self.state.output[dest] = arg_values[0]
        else:
            self.state.output[dest] = arg_values

        return True

    def _consume_argument(
        self,
        arg: _arguments.ArgumentDefinition,
        args_deque: deque[str],
        subparser_frontier: dict[str, _parsers.SubparsersSpecification],
    ) -> list[str]:
        """Consume values for an argument based on its nargs specification.

        Args:
            arg: The argument definition.
            args_deque: Remaining arguments to consume from.
            subparser_frontier: Current subparser frontier.

        Returns:
            List of consumed argument values.

        Raises:
            SystemExit: If required values are missing or invalid.
        """
        arg_values: list[str] = []

        # Consume arguments based on nargs.
        # https://docs.python.org/3/library/argparse.html#nargs
        if isinstance(arg.lowered.nargs, int):
            for _ in range(arg.lowered.nargs):
                if len(args_deque) == 0:
                    _help_formatting.error_and_exit(
                        f"Missing value for argument '{arg.lowered.name_or_flags}'. "
                        f"Expected {arg.lowered.nargs} values.",
                        prog=self.prog,
                        console_outputs=self.console_outputs,
                        add_help=self.parser_spec.add_help,
                    )
                arg_values.append(args_deque.popleft())
        elif arg.lowered.nargs in ("*", "?"):
            counter = 0
            while (
                len(args_deque) > 0
                and args_deque[0] not in self.maps.dest_from_flag
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
                )
            ):
                arg_values.append(args_deque.popleft())
                counter += 1

        # Validate choices if present.
        if arg.lowered.choices is not None:
            for value in arg_values:
                if value not in arg.lowered.choices:
                    _help_formatting.error_and_exit(
                        "Invalid choice",
                        f"invalid choice '{value}' for argument '{arg.lowered.name_or_flags}'. "
                        f"Expected one of {arg.lowered.choices}.",
                        prog=self.prog,
                        console_outputs=self.console_outputs,
                        add_help=self.parser_spec.add_help,
                    )

        return arg_values

    def _show_help(
        self,
        subparser_frontier: dict[str, _parsers.SubparsersSpecification],
    ) -> None:
        """Display help message.

        Args:
            subparser_frontier: Current subparser frontier for context.
        """
        if self.console_outputs:
            prog = self.prog if self.prog is not None else sys.argv[0]
            print(
                *_help_formatting.format_help(
                    prog=prog,
                    description=self.parser_spec.description,
                    args=_help_formatting.build_args_from_parser_specs(
                        [self.parser_spec]
                    ),
                    subparser_frontier=subparser_frontier,
                    is_root=self.parser_spec.intern_prefix == "",
                ),
                sep="\n",
            )

    def validate_required_args(self) -> None:
        """Validate that all required arguments were provided.

        Raises:
            SystemExit: If required arguments are missing.
        """
        missing_required_args: list[str] = []

        # Check for missing mutex groups.
        missing_mutex_groups = set(self.maps.required_mutex_flags.keys()) - set(
            self.state.observed_mutex_groups.keys()
        )
        for missing_group in missing_mutex_groups:
            missing_required_args.append(
                "{" + ",".join(self.maps.required_mutex_flags[missing_group]) + "}"
            )

        # Check for missing keyword arguments.
        for dest, arg in self.maps.kwarg_from_dest.items():
            if dest in self.state.output:
                continue

            if arg.lowered.required is True:
                missing_required_args.append(arg.lowered.name_or_flags[-1])
            else:
                # Use default value (will be applied in _calling.py).
                self.state.output[dest] = arg.lowered.default

        if len(missing_required_args) > 0:
            _help_formatting.required_args_error(
                prog=self.prog,
                required_args=missing_required_args,
                args=list(self.args),
                parser_spec=self.parser_spec,
                console_outputs=self.console_outputs,
            )

        # Apply defaults for positional arguments.
        for arg in self.maps.positional_args:
            if arg.lowered.name_or_flags[-1] not in self.state.output:
                self.state.output[arg.lowered.name_or_flags[-1]] = arg.lowered.default

    def handle_unknown_args(
        self,
        return_unknown_args: bool,
    ) -> None:
        """Handle unknown arguments found during parsing.

        Args:
            return_unknown_args: If False, error on unknown args. If True, collect them.

        Raises:
            SystemExit: If return_unknown_args is False and unknown args were found.
        """
        if not return_unknown_args and len(self.state.unknown_args_and_progs) > 0:
            assert self.full_args is not None, (
                "full_args should be set in __post_init__"
            )
            assert self.root_parser_spec is not None, (
                "root_parser_spec should be set in __post_init__"
            )
            _help_formatting.unrecognized_args_error(
                prog=self.prog,
                unrecognized_args_and_progs=self.state.unknown_args_and_progs,
                args=list(self.full_args),
                parser_spec=self.root_parser_spec,
                console_outputs=self.console_outputs,
            )


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
        """Unified single-pass recursive parser with cascading args support.

        Arguments have different visibility scopes:
        - Standard args: visible at their parser level only
        - CascadingSubcommandArgs (per-argument): cascade downward to descendants
        - CascadingSubcommandArgs (parser-level wrapper): consolidates selected subcommand args upward

        Cascading args are registered dynamically during parsing to avoid
        expensive upfront tree traversal.
        """
        # Parse recursively with empty initial cascading dict.
        # Cascading args are collected and passed down as we traverse.
        output, unknown_args_and_progs = self._parse_args_recursive(
            parser_spec=parser_spec,
            args=args,
            prog=prog,
            return_unknown_args=return_unknown_args,
            console_outputs=console_outputs,
            cascading_args_from_parents={},
            subparser_frontier=parser_spec.subparsers_from_intern_prefix,
            full_args=args,
            root_parser_spec=parser_spec,
        )

        return output, unknown_args_and_progs

    def _parse_args_recursive(
        self,
        parser_spec: _parsers.ParserSpecification,
        args: Sequence[str],
        prog: str,
        return_unknown_args: bool,
        console_outputs: bool,
        cascading_args_from_parents: dict[str, _arguments.ArgumentDefinition],
        subparser_frontier: dict[str, _parsers.SubparsersSpecification],
        full_args: Sequence[str],
        root_parser_spec: _parsers.ParserSpecification,
        shared_state: ParsingState | None = None,
    ) -> tuple[dict[str | None, Any], list[tuple[str, str]] | None]:
        """Recursive parser with cascading args support and free intermixing.

        Args:
            parser_spec: The parser specification for this level.
            args: Remaining arguments to parse.
            prog: Program name for error messages.
            return_unknown_args: Whether to return unknown args or error.
            console_outputs: Whether to output to console.
            cascading_args_from_parents: Cascading args from parent parsers (passed down).
            subparser_frontier: Current subparser frontier.
            full_args: Full argument list for error messages.
            root_parser_spec: Root parser for error messages.
            shared_state: Shared parsing state across all recursion levels.
        """
        # Phase 1: Create or reuse parsing state (shared across all levels).
        if shared_state is None:
            shared_state = ParsingState()

        # Create parsing context and register arguments.
        ctx = ParsingContext(
            parser_spec=parser_spec,
            args=args,
            prog=prog,
            console_outputs=console_outputs,
            full_args=full_args,
            root_parser_spec=root_parser_spec,
        )
        # Use the shared state instead of creating a new one.
        ctx.state = shared_state

        # Register cascading args from parent levels.
        for arg in cascading_args_from_parents.values():
            ctx.register_argument(arg)

        # Build new cascading dict for children by adding this level's cascading args.
        cascading_args_for_children = cascading_args_from_parents.copy()

        # Register this parser's args (skip ones already in cascading_args_from_parents).
        for arg in parser_spec.get_args_including_children():
            # Check if this arg was already registered via cascading_args_from_parents.
            arg_dest = arg.lowered.dest if not arg.is_positional() else arg.lowered.name_or_flags[0]
            if arg_dest not in cascading_args_from_parents:
                ctx.register_argument(arg)

            # If this arg has per-argument CascadingSubcommandArgs marker, add to cascading dict.
            if conf._markers.CascadingSubcommandArgs in arg.field.markers:
                if arg_dest in cascading_args_for_children:
                    existing_arg = cascading_args_for_children[arg_dest]
                    # Only raise error if it's a different arg (not the same one).
                    if existing_arg is not arg:
                        raise ValueError(
                            f"Conflicting cascading arguments: "
                            f"'{existing_arg.field.intern_name}' and '{arg.field.intern_name}' "
                            f"both cascade to destination '{arg_dest}'"
                        )
                else:
                    cascading_args_for_children[arg_dest] = arg

        # For free intermixing of per-argument cascading args, collect them from direct
        # subparser children. This allows specifying subcommand args before the subcommand.
        # Note: We only traverse direct children (one level), not the entire tree.
        for subparser_spec in parser_spec.subparsers_from_intern_prefix.values():
            for child_parser in subparser_spec.parser_from_name.values():
                for arg in child_parser.get_args_including_children():
                    if conf._markers.CascadingSubcommandArgs in arg.field.markers:
                        arg_dest = arg.lowered.dest if not arg.is_positional() else arg.lowered.name_or_flags[0]
                        if arg_dest not in ctx.maps.kwarg_from_dest and arg not in ctx.maps.positional_args:
                            # Register at current level for free intermixing.
                            ctx.register_argument(arg)
                            if arg_dest not in cascading_args_for_children:
                                cascading_args_for_children[arg_dest] = arg

        # Handle default subcommands upfront by registering their args.
        # This allows parsing default subcommand args even when the subcommand isn't specified.
        for intern_prefix, subparser_spec in subparser_frontier.items():
            if subparser_spec.default_name is not None:
                dest = _strings.make_subparser_dest(intern_prefix)
                if dest not in shared_state.output:
                    default_parser = subparser_spec.parser_from_name[subparser_spec.default_name]
                    # Register args from default parser (similar to when subcommand is selected).
                    for arg in default_parser.get_args_including_children():
                        arg_dest = arg.lowered.dest if not arg.is_positional() else arg.lowered.name_or_flags[0]
                        if arg_dest not in ctx.maps.kwarg_from_dest and arg not in ctx.maps.positional_args:
                            ctx.register_argument(arg)

        ctx.add_help_flags()

        # Track selected subparsers for later recursion (for validation/defaults).
        selected_subparsers: list[tuple[_parsers.ParserSpecification, str]] = []

        # Phase 3: Main parsing loop with free intermixing.
        args_deque = deque(args)
        while len(args_deque) > 0:
            arg_value_peek = args_deque[0]

            # Try parsing as count flag (e.g., -vvv).
            if ctx.try_parse_count_flag(arg_value_peek, args_deque):
                continue

            # Try parsing as keyword argument.
            if ctx.try_parse_keyword_arg(
                arg_value_peek, args_deque, subparser_frontier
            ):
                continue

            # Try parsing --flag=value syntax.
            if ctx.try_parse_flag_equals_value(arg_value_peek, args_deque):
                continue

            # Check for subparsers in frontier.
            subparser_found = False
            for intern_prefix, subparser_spec in subparser_frontier.items():
                if arg_value_peek in subparser_spec.parser_from_name:
                    args_deque.popleft()
                    ctx.state.output[_strings.make_subparser_dest(intern_prefix)] = (
                        arg_value_peek
                    )

                    # Build new frontier: remove this group, add child's groups.
                    chosen_parser = subparser_spec.parser_from_name[arg_value_peek]
                    new_frontier = {
                        k: v
                        for k, v in subparser_frontier.items()
                        if k != intern_prefix
                    }
                    new_frontier.update(chosen_parser.subparsers_from_intern_prefix)

                    # Update frontier for subsequent parsing.
                    subparser_frontier = new_frontier

                    # For parser-level cascading (wrapper usage), collect ALL args from
                    # the selected subparser and make them visible at the current level.
                    # For per-argument cascading, only collect args with the marker.
                    # This implements the old ConsolidateSubcommandArgs behavior.
                    has_parser_level_cascading = (
                        conf._markers.CascadingSubcommandArgs in root_parser_spec.markers
                    )

                    # Check if the chosen parser has any cascading args.
                    has_cascading_args_in_chosen = any(
                        conf._markers.CascadingSubcommandArgs in arg.field.markers
                        for arg in chosen_parser.get_args_including_children()
                    )

                    # Determine if we should consolidate args from this subparser.
                    # Consolidate if:
                    # 1. Parser-level cascading, OR
                    # 2. This subparser has any per-argument cascading args (for backward compat)
                    should_consolidate_all = (
                        has_parser_level_cascading or has_cascading_args_in_chosen
                    )

                    # Collect args from the chosen parser to make them visible at current level.
                    for arg in chosen_parser.get_args_including_children():
                        if should_consolidate_all:
                            # Consolidate ALL args (backward compat with old ConsolidateSubcommandArgs).
                            arg_dest = arg.lowered.dest if not arg.is_positional() else arg.lowered.name_or_flags[0]
                            if arg_dest not in ctx.maps.kwarg_from_dest and arg not in ctx.maps.positional_args:
                                # Register in current context to make it visible at current level.
                                ctx.register_argument(arg)
                                # Add cascading args to dict for children.
                                if conf._markers.CascadingSubcommandArgs in arg.field.markers:
                                    cascading_args_for_children[arg_dest] = arg
                        elif conf._markers.CascadingSubcommandArgs in arg.field.markers:
                            # Only consolidate args with the marker (new cascading behavior).
                            arg_dest = arg.lowered.dest if not arg.is_positional() else arg.lowered.name_or_flags[0]
                            if arg_dest not in ctx.maps.kwarg_from_dest and arg not in ctx.maps.positional_args:
                                ctx.register_argument(arg)
                                cascading_args_for_children[arg_dest] = arg

                    # Track the selected parser for later recursion.
                    selected_subparsers.append((chosen_parser, prog + " " + arg_value_peek))

                    # Don't recurse immediately - continue parsing at current level.
                    # We'll recurse later to validate/apply defaults in the selected subparser.
                    subparser_found = True
                    break

            if subparser_found:
                # Don't break - continue parsing at current level with new args registered.
                continue

            # Try parsing as positional argument.
            if ctx.try_parse_positional_arg(args_deque, subparser_frontier):
                continue

            # If we get here, it's an unrecognized argument.
            args_deque.popleft()
            ctx.state.unknown_args_and_progs.append((arg_value_peek, prog))

        # Recurse into selected subparsers to validate/apply defaults.
        for chosen_parser, chosen_prog in selected_subparsers:
            _, _ = self._parse_args_recursive(
                parser_spec=chosen_parser,
                args=[],  # No args left - just validating
                prog=chosen_prog,
                return_unknown_args=False,
                console_outputs=console_outputs,
                cascading_args_from_parents=cascading_args_for_children,
                subparser_frontier=chosen_parser.subparsers_from_intern_prefix,
                full_args=full_args,
                root_parser_spec=root_parser_spec,
                shared_state=shared_state,
            )

        # Handle unknown arguments.
        ctx.handle_unknown_args(return_unknown_args)

        # Handle default subcommands.
        for intern_prefix, subparser_spec in subparser_frontier.items():
            dest = _strings.make_subparser_dest(intern_prefix)
            if dest not in ctx.state.output:
                default_subcommand = subparser_spec.default_name
                if default_subcommand is None:
                    # No default available; this is an error.
                    _help_formatting.error_and_exit(
                        "Missing subcommand",
                        f"Expected subcommand from {list(subparser_spec.parser_from_name.keys())}, "
                        f"but none was provided.",
                        prog=prog,
                        console_outputs=console_outputs,
                        add_help=parser_spec.add_help,
                    )
                else:
                    ctx.state.output[dest] = default_subcommand
                    default_parser = subparser_spec.parser_from_name[default_subcommand]

                    # Build new frontier.
                    new_frontier = {
                        k: v
                        for k, v in subparser_frontier.items()
                        if k != intern_prefix
                    }
                    new_frontier.update(default_parser.subparsers_from_intern_prefix)

                    # Recurse with shared state.
                    _, _ = self._parse_args_recursive(
                        parser_spec=default_parser,
                        args=[],
                        prog=prog + " " + default_subcommand,
                        return_unknown_args=False,
                        console_outputs=console_outputs,
                        cascading_args_from_parents=cascading_args_for_children,
                        subparser_frontier=new_frontier,
                        full_args=full_args,
                        root_parser_spec=root_parser_spec,
                        shared_state=shared_state,
                    )
                    # No need to update - sharing same state.

        # Validate required arguments and apply defaults.
        ctx.validate_required_args()

        return (
            shared_state.output,
            shared_state.unknown_args_and_progs if return_unknown_args else None,
        )

    def _gather_activated_parsers(
        self,
        args: Sequence[str],
        initial_frontier: dict[str, _parsers.SubparsersSpecification],
        subcommand_selections: dict[str, str],
        prog: str,
        console_outputs: bool,
    ) -> list[_parsers.ParserSpecification]:
        """Recursively find all parsers activated by subcommand selections.

        In consolidated mode, subcommands must come before other arguments.
        This matches argparse behavior and enables better error detection.

        Args:
            args: All command-line arguments.
            initial_frontier: Starting subparser frontier.
            subcommand_selections: Output dict to record selections.
            prog: Program name for error messages.
            console_outputs: Whether to output to console.

        Returns:
            List of all activated parser specifications.

        Raises:
            SystemExit: If invalid subcommands are found or subcommands appear after arguments.
        """
        consumed_args: set[int] = set()
        subcommand_phase_ended_by: list[str | None] = [
            None
        ]  # Track what ended the phase.

        def gather(
            current_frontier: dict[str, _parsers.SubparsersSpecification],
        ) -> list[_parsers.ParserSpecification]:
            activated = []

            for idx, arg in enumerate(args):
                if idx in consumed_args:
                    continue

                # Check if this is a valid subcommand in the current frontier.
                found_subcommand = False
                for intern_prefix, subparser_spec in current_frontier.items():
                    if arg in subparser_spec.parser_from_name:
                        # Enforce subcommands-first ordering.
                        if subcommand_phase_ended_by[0] is not None:
                            error_msg = (
                                f"Subcommand '{arg}' appears after other arguments. "
                                f"In consolidated mode, all subcommands must come before other arguments."
                            )
                            if subcommand_phase_ended_by[0]:
                                error_msg += f" ('{subcommand_phase_ended_by[0]}' is not a valid subcommand)"
                            _help_formatting.error_and_exit(
                                "Misplaced subcommand",
                                error_msg,
                                prog=prog,
                                console_outputs=console_outputs,
                                add_help=True,
                            )

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
                        new_frontier.update(chosen_parser.subparsers_from_intern_prefix)

                        activated.extend(gather(new_frontier))
                        found_subcommand = True
                        break

                if found_subcommand:
                    continue

                # This argument is not a valid subcommand in the current frontier.
                # Mark that the subcommand phase has ended - all subsequent arguments
                # should be flags/values, not subcommands.
                if subcommand_phase_ended_by[0] is None:
                    subcommand_phase_ended_by[0] = arg

            return activated

        return gather(initial_frontier)

    def _show_consolidated_help(
        self,
        parser_spec: _parsers.ParserSpecification,
        prog: str,
        args: Sequence[str],
        args_deque: deque[str],
        subparser_frontier: dict[str, _parsers.SubparsersSpecification],
        console_outputs: bool,
    ) -> None:
        """Show help in consolidated mode, including activated parsers.

        Args:
            parser_spec: Root parser specification.
            prog: Program name.
            args: All command-line arguments.
            args_deque: Remaining arguments deque.
            subparser_frontier: Current subparser frontier.
            console_outputs: Whether to output to console.
        """
        # Gather activated parsers based on subcommands seen before --help.
        args_before_help = args[: len(args) - len(args_deque)]
        subcommand_selections: dict[str, str] = {}

        activated_parsers = self._gather_activated_parsers(
            args_before_help,
            subparser_frontier,
            subcommand_selections,
            prog,
            console_outputs,
        )

        # Build the updated frontier after activations.
        help_frontier = dict(subparser_frontier)
        for intern_prefix in subcommand_selections:
            del help_frontier[intern_prefix]
        for parser in activated_parsers:
            help_frontier.update(parser.subparsers_from_intern_prefix)

        # Build prog string including selected subcommands.
        help_prog = prog if prog is not None else sys.argv[0]
        for subcommand_name in subcommand_selections.values():
            help_prog += " " + subcommand_name

        # Show help with root + activated parsers.
        if console_outputs:
            print(
                *_help_formatting.format_help(
                    prog=help_prog,
                    description=parser_spec.description,
                    args=_help_formatting.build_args_from_parser_specs(
                        [parser_spec] + activated_parsers
                    ),
                    subparser_frontier=help_frontier,
                    is_root=parser_spec.intern_prefix == "",
                ),
                sep="\n",
            )

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
