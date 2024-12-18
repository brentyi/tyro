"""The :mod:`tyro.conf` submodule contains helpers for attaching parsing-specific
configuration metadata to types via `PEP 593 <https://peps.python.org/pep-0593/>`_ runtime
annotations.

Flags will be applied recursively, and can be used one of multiple ways:

1. They can be subscripted: ``tyro.conf.FlagConversionoff[bool]``.
2. They can be passed into :py:data:`typing.Annotated`: ``Annotated[str, tyro.conf.FlagConversionOff]``.
3. They can be passed into :func:`tyro.cli`: ``tyro.cli(Args, config=(tyro.conf.FlagConversionOff,))``.

Features here are supported, but generally unnecessary and should be used sparingly.
"""

from ._confstruct import arg as arg
from ._confstruct import subcommand as subcommand
from ._markers import AvoidSubcommands as AvoidSubcommands
from ._markers import ConsolidateSubcommandArgs as ConsolidateSubcommandArgs
from ._markers import EnumChoicesFromValues as EnumChoicesFromValues
from ._markers import Fixed as Fixed
from ._markers import FlagConversionOff as FlagConversionOff
from ._markers import OmitArgPrefixes as OmitArgPrefixes
from ._markers import OmitSubcommandPrefixes as OmitSubcommandPrefixes
from ._markers import Positional as Positional
from ._markers import PositionalRequiredArgs as PositionalRequiredArgs
from ._markers import Suppress as Suppress
from ._markers import SuppressFixed as SuppressFixed
from ._markers import UseAppendAction as UseAppendAction
from ._markers import UseCounterAction as UseCounterAction
from ._markers import configure as configure
