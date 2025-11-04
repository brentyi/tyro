"""Base interface for shell completion generation."""

from __future__ import annotations

import abc

from ... import _parsers


class CompletionGenerator(abc.ABC):
    """Abstract base class for shell completion generators."""

    @abc.abstractmethod
    def generate(
        self,
        parser_spec: _parsers.ParserSpecification,
        prog: str,
        root_prefix: str,
    ) -> str:
        """Generate a shell completion script.

        Args:
            parser_spec: Parser specification to generate completion for.
            prog: Program name.
            root_prefix: Prefix for completion function names.

        Returns:
            Shell completion script as a string.
        """
        ...
