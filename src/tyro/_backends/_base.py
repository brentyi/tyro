"""Backend abstraction for parsing command-line arguments.

The backend interface separates parsing from instantiation. Both backends parse
command-line arguments into string values, which are then passed to _calling.py
for object instantiation. This separation provides several benefits:

1. Clean separation of concerns between parsing and instantiation.
2. Reuse of existing instantiation logic in _calling.py.
3. Ability to handle --help without instantiating objects (avoiding side effects).
4. Easier debugging with inspectable intermediate string values.
5. Consistent interface between different backend implementations.
"""

from __future__ import annotations

import abc
from typing import Any, Sequence

from tyro._backends._argparse_formatter import TyroArgumentParser

from .. import _parsers


class ParserBackend(abc.ABC):
    """Abstract base class for parser backends.

    All backends follow a two-phase approach:
    1. Parse command-line arguments into string values (handled by the backend).
    2. Instantiate objects from parsed values (handled by _calling.py).

    This design ensures backends are interchangeable and can leverage existing
    instantiation logic without duplication.
    """

    @abc.abstractmethod
    def parse_args(
        self,
        parser_spec: _parsers.ParserSpecification,
        args: Sequence[str],
        prog: str,
        return_unknown_args: bool,
        console_outputs: bool,
    ) -> tuple[dict[str | None, Any], list[str] | None]:
        """Parse command-line arguments using the parser specification.

        Args:
            parser_spec: Specification for the parser structure.
            args: Command-line arguments to parse.
            prog: Program name for help text.
            return_unknown_args: If True, return unknown arguments.
            console_outputs: If True, allow console outputs (help, errors).

        Returns:
            A tuple of (parsed_values, unknown_args).
            parsed_values is a dict mapping field names to string values or
            lists of strings (for multi-value arguments).
            unknown_args is None unless return_unknown_args is True.
        """
        ...

    @abc.abstractmethod
    def get_parser_for_completion(
        self,
        parser_spec: _parsers.ParserSpecification,
        prog: str | None,
        add_help: bool,
    ) -> TyroArgumentParser:
        """Get a parser object for shell completion generation.

        This is needed for compatibility with shtab completion generation.

        Args:
            parser_spec: Specification for the parser structure.
            prog: Program name for help text.

        Returns:
            A parser object compatible with shtab (typically argparse.ArgumentParser).
        """
        ...
