"""Argparse-based backend for parsing command-line arguments."""

from __future__ import annotations

import contextlib
import sys
import time
from typing import Any, Sequence

from .. import _parsers
from . import _argparse as argparse
from . import _argparse_formatter
from ._base import ParserBackend

# Timing helper for benchmarking.
ENABLE_TIMING = False


def enable_timing(enable: bool) -> None:
    """Enable or disable timing for the argparse backend."""
    global ENABLE_TIMING
    ENABLE_TIMING = enable


@contextlib.contextmanager
def timing_context(name: str):
    """Context manager to time a block of code."""
    if not ENABLE_TIMING:
        yield
        return

    start_time = time.perf_counter()
    yield
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    print(f"{name} took {elapsed_time:.4f} seconds", file=sys.stderr, flush=True)


class ArgparseBackend(ParserBackend):
    """Backend that uses argparse for parsing command-line arguments.

    This is the original implementation, which constructs an argparse.ArgumentParser
    from the ParserSpecification and uses it to parse arguments. While robust and
    well-tested, it can be slow for complex command structures with many subcommands.
    """

    def parse_args(
        self,
        parser_spec: _parsers.ParserSpecification,
        args: Sequence[str],
        prog: str,
        return_unknown_args: bool,
        console_outputs: bool,
    ) -> tuple[dict[str | None, Any], list[str] | None]:
        """Parse command-line arguments using argparse."""

        with timing_context("Construct parser"):
            # Create and configure the argparse parser.
            parser = _argparse_formatter.TyroArgumentParser(
                prog=prog,
                allow_abbrev=False,
            )
            parser._parser_specification = parser_spec
            parser._parsing_known_args = return_unknown_args
            parser._console_outputs = console_outputs
            parser._args = list(args)

            # Apply the parser specification to populate the argparse parser.
            parser_spec.apply(parser, force_required_subparsers=False)

        # Parse the arguments.
        if return_unknown_args:
            namespace, unknown_args = parser.parse_known_args(args=args)
        else:
            namespace = parser.parse_args(args=args)
            unknown_args = None

        # Convert namespace to dictionary.
        value_from_prefixed_field_name = vars(namespace)

        return value_from_prefixed_field_name, unknown_args

    def get_parser_for_completion(
        self,
        parser_spec: _parsers.ParserSpecification,
        prog: str | None = None,
    ) -> argparse.ArgumentParser:
        """Get an argparse parser for shell completion generation."""

        parser = _argparse_formatter.TyroArgumentParser(
            prog=prog,
            allow_abbrev=False,
        )
        parser._parser_specification = parser_spec
        parser._parsing_known_args = False
        parser._console_outputs = True
        parser._args = []

        # Apply the parser specification to populate the argparse parser.
        parser_spec.apply(parser, force_required_subparsers=False)

        return parser
