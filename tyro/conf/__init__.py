"""The :mod:`tyro.conf` submodule contains helpers for attaching parsing-specific
configuration metadata to types via [PEP 593](https://peps.python.org/pep-0593/) runtime
annotations.

Configuration flags are applied recursively, and should generally be subscripted:
`Fixed[T]`, `Suppress[T]`, etc.

Features here are supported, but generally unnecessary and should be used sparingly.
"""

from ._confstruct import arg, subcommand
from ._markers import (
    AvoidSubcommands,
    ConsolidateSubcommandArgs,
    Fixed,
    FlagConversionOff,
    OmitSubcommandPrefixes,
    Positional,
    Suppress,
    SuppressFixed,
    configure,
)

__all__ = [
    "arg",
    "subcommand",
    "AvoidSubcommands",
    "ConsolidateSubcommandArgs",
    "Fixed",
    "FlagConversionOff",
    "OmitSubcommandPrefixes",
    "Positional",
    "Suppress",
    "SuppressFixed",
    "configure",
]
