"""The :mod:`dcargs.conf` submodule contains helpers for attaching parsing-specific
configuration metadata to types via PEP 593 runtime annotations.

Features here are supported, but are generally unnecessary and should be used sparingly.
"""

from ._markers import AvoidSubcommands, Fixed, FlagConversionOff
from ._subcommands import subcommand

__all__ = [
    "AvoidSubcommands",
    "Fixed",
    "FlagConversionOff",
    "subcommand",
]
