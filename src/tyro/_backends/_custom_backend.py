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

from tyro._strings import make_subparser_dest

from .. import _arguments, _parsers
from . import _argparse as argparse
from . import _help_formatting
from ._base import ParserBackend


class CustomBackend(ParserBackend):
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

        out, unknown_args = self._parse_args(
            parser_spec,
            args,
            prog,
            return_unknown_args=return_unknown_args,
            console_outputs=console_outputs,
        )
        if unknown_args is not None:
            unknown_args = [arg[0] for arg in unknown_args]
        return out, unknown_args

    def _parse_args(
        self,
        parser_spec: _parsers.ParserSpecification,
        args: Sequence[str],
        prog: str,
        return_unknown_args: bool,
        console_outputs: bool,
    ) -> tuple[dict[str | None, Any], list[tuple[str, str]] | None]:
        self.args = args
        self.console_outputs = console_outputs

        output: dict[str | None, list[str] | bool | str | int | None] = {}

        positional_args: deque[_arguments.ArgumentDefinition] = deque()
        kwarg_from_dest: dict[str, _arguments.ArgumentDefinition] = {}
        dest_from_flag: dict[str, str] = {}
        value_from_boolean_flag: dict[str, bool] = {}

        def recurse_children(
            parser_spec: _parsers.ParserSpecification, traversing_up: bool
        ) -> None:
            if (
                parser_spec.consolidate_subcommand_args
                and parser_spec.subparsers is not None
                and not traversing_up
            ):
                return

            for arg in parser_spec.get_args_including_children():
                if arg.is_suppressed():
                    continue

                if arg.lowered.action == "append":
                    output[
                        arg.lowered.name_or_flags[-1]
                        if arg.field.is_positional()
                        else arg.lowered.dest
                    ] = []
                elif arg.lowered.action == "count":
                    output[arg.lowered.dest] = 0

                if arg.field.is_positional():
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
            if (
                parser_spec.consolidate_subcommand_args
                and parser_spec.subparser_parent is not None
            ):
                recurse_children(parser_spec.subparser_parent, traversing_up=True)

        recurse_children(parser_spec, traversing_up=False)

        # Add help flag to dest_from_flag. This is used for "is valid flag" checks.
        dest_from_flag["-h"] = "__help__"
        dest_from_flag["--help"] = "__help__"

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
                if arg_value_peek in ("-h", "--help"):
                    # Help flag.
                    if console_outputs:
                        print(
                            *_help_formatting.format_help(
                                parser_spec,
                                prog=prog if prog is not None else sys.argv[0],
                            ),
                            sep="\n",
                        )
                    sys.exit(0)
                elif arg_value_peek in value_from_boolean_flag:
                    # --flag or --no-flag.
                    args_deque.popleft()
                    arg = kwarg_from_dest[dest_from_flag[arg_value_peek]]
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
                    dest = arg.lowered.dest
                    arg_values = self._consume_argument(
                        arg, args_deque, dest_from_flag, prog
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

            # Check for subparsers.
            if (
                parser_spec.subparsers is not None
                and arg_value_peek in parser_spec.subparsers.parser_from_name
            ):
                args_deque.popleft()
                output[make_subparser_dest(parser_spec.subparsers.intern_prefix)] = (
                    arg_value_peek
                )
                inner_output, inner_unknown_args = self._parse_args(
                    parser_spec.subparsers.parser_from_name[arg_value_peek],
                    args_deque,
                    prog=prog + " " + arg_value_peek,
                    return_unknown_args=True,
                    console_outputs=console_outputs,
                )
                assert inner_unknown_args is not None
                output.update(inner_output)
                unknown_args_and_progs.extend(inner_unknown_args)
                subparser_found = True
                break

            # Handle positional arguments.
            if len(positional_args) > 0:
                arg = positional_args.popleft()
                assert arg.lowered.dest is None
                dest = arg.lowered.name_or_flags[-1]
                arg_values = self._consume_argument(
                    arg, args_deque, dest_from_flag, prog
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

        # Expected subcommand, but none was found.
        if parser_spec.subparsers is not None and not subparser_found:
            default_subcommand = parser_spec.subparsers.default_name
            if default_subcommand is None:
                # No subcommand was found.
                _help_formatting.error_and_exit(
                    "Missing subcommand",
                    f"Expected subcommand from {list(parser_spec.subparsers.parser_from_name.keys())}, "
                    f"but found: {args_deque[0] if len(args_deque) > 0 else 'nothing'}.",
                    prog=prog,
                    console_outputs=console_outputs,
                )
            else:
                # Specify default subcommand.
                output[make_subparser_dest(parser_spec.subparsers.intern_prefix)] = (
                    default_subcommand
                )
                inner_output, inner_unknown_args = self.parse_args(
                    parser_spec.subparsers.parser_from_name[default_subcommand],
                    [],
                    prog=prog + " " + default_subcommand,
                    return_unknown_args=False,
                    console_outputs=console_outputs,
                )
                output.update(inner_output)
                del inner_unknown_args

        # Go through remaining keyword arguments.
        missing_required_args: list[str] = []
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

    def get_parser_for_completion(
        self,
        parser_spec: _parsers.ParserSpecification,
        prog: str | None = None,
    ) -> argparse.ArgumentParser:
        """Get an argparse parser for shell completion generation.

        Since shtab requires an argparse parser, we still need to create one
        for completion generation. This is only used when generating completions,
        not during normal parsing.
        """
        from ._argparse_backend import ArgparseBackend

        return ArgparseBackend().get_parser_for_completion(parser_spec, prog=prog)

    def _consume_argument(
        self,
        arg: _arguments.ArgumentDefinition,
        args_deque: deque[str],
        dest_from_flag: dict[str, str],
        prog: str,
    ) -> list[str]:
        arg_values: list[str] = []

        # Consume arguments based on nargs.
        # https://docs.python.org/3/library/argparse.html#nargs
        if isinstance(arg.lowered.nargs, int):
            for _ in range(arg.lowered.nargs):
                if len(args_deque) == 0:
                    _help_formatting.error_and_exit(
                        f"Missing value for argument '{arg.lowered.dest}'. "
                        f"Expected {arg.lowered.nargs} values.",
                        prog=prog,
                        console_outputs=self.console_outputs,
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
            ):
                arg_values.append(args_deque.popleft())
                counter += 1

        # If present: make sure arguments are in choices.
        if arg.lowered.choices is not None:
            for value in arg_values:
                if value not in arg.lowered.choices:
                    _help_formatting.error_and_exit(
                        "Invalid choice",
                        f"invalid choice '{value}' for argument '{arg.lowered.dest}'. "
                        f"Expected one of {arg.lowered.choices}.",
                        prog=prog,
                        console_outputs=self.console_outputs,
                    )

        return arg_values
