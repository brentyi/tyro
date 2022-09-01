"""The :mod:`dcargs.metadata` submodule contains helpers for attaching parsing-specific
metadata to types.

Features here are supported, but generally should be unnecessary.
"""

from ._markers import Fixed, FlagsOff, SubcommandsOff
from ._subcommands import subcommand

__all__ = [
    "Fixed",
    "FlagsOff",
    "SubcommandsOff",
    "subcommand",
]
