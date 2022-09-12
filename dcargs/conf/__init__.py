"""The :mod:`dcargs.conf` submodule contains helpers for attaching parsing-specific
configuration metadata to types via [PEP 593](https://peps.python.org/pep-0593/) runtime
annotations.

Features here are supported, but generally unnecessary and should be used sparingly.
"""

from ._markers import AvoidSubcommands, Fixed, FlagConversionOff, Positional, Suppress
from ._subcommands import subcommand

__all__ = [
    "AvoidSubcommands",
    "Fixed",
    "FlagConversionOff",
    "Positional",
    "Suppress",
    "subcommand",
]
