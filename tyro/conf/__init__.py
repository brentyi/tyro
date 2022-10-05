"""The :mod:`tyro.conf` submodule contains helpers for attaching parsing-specific
configuration metadata to types via [PEP 593](https://peps.python.org/pep-0593/) runtime
annotations.

Configuration flags are applied recursively, and should generally be subscripted:
`Fixed[T]`, `Suppress[T]`, etc.

Features here are supported, but generally unnecessary and should be used sparingly.
"""

from ._markers import (
    AvoidSubcommands,
    Fixed,
    FlagConversionOff,
    OmitSubcommandPrefixes,
    Positional,
    Suppress,
    SuppressFixed,
)
from ._subcommands import subcommand

__all__ = [
    "AvoidSubcommands",
    "Fixed",
    "FlagConversionOff",
    "OmitSubcommandPrefixes",
    "Positional",
    "Suppress",
    "SuppressFixed",
    "subcommand",
]
