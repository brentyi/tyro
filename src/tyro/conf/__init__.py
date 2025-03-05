"""The :mod:`tyro.conf` submodule contains helpers for attaching parsing-specific
configuration metadata to types via `PEP 593 <https://peps.python.org/pep-0593/>`_ runtime
annotations.

Configuration markers allow you to customize generated CLI interfaces, such as
to set positional arguments, suppress fields, or change boolean flag behaviors.

Markers can be applied in three ways:

1. They can be subscripted directly: ``tyro.conf.FlagConversionOff[bool]``
2. They can be passed into :py:data:`typing.Annotated`: ``Annotated[str, tyro.conf.Positional]``
3. They can be passed into :func:`tyro.cli`: ``tyro.cli(Args, config=(tyro.conf.FlagConversionOff,))``

Markers are applied recursively to nested structures.

These features are fully supported but should be used sparingly. Prefer using
standard Python type annotations whenever possible.

See :doc:`/examples/basics` for examples of using configuration markers.
"""

from ._confstruct import arg as arg
from ._confstruct import subcommand as subcommand
from ._markers import AvoidSubcommands as AvoidSubcommands
from ._markers import ConsolidateSubcommandArgs as ConsolidateSubcommandArgs
from ._markers import EnumChoicesFromValues as EnumChoicesFromValues
from ._markers import Fixed as Fixed
from ._markers import FlagConversionOff as FlagConversionOff
from ._markers import FlagCreatePairsOff as FlagCreatePairsOff
from ._markers import HelptextFromCommentsOff as HelptextFromCommentsOff
from ._markers import OmitArgPrefixes as OmitArgPrefixes
from ._markers import OmitSubcommandPrefixes as OmitSubcommandPrefixes
from ._markers import Positional as Positional
from ._markers import PositionalRequiredArgs as PositionalRequiredArgs
from ._markers import Suppress as Suppress
from ._markers import SuppressFixed as SuppressFixed
from ._markers import UseAppendAction as UseAppendAction
from ._markers import UseCounterAction as UseCounterAction
from ._markers import configure as configure
