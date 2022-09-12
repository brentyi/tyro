from typing import Type, TypeVar

from typing_extensions import Annotated

from .. import _singleton


class Marker(_singleton.Singleton):
    pass


def _make_marker(description: str) -> Marker:
    class _InnerMarker(Marker):
        def __repr__(self):
            return description

    return _InnerMarker()


# Current design issue: markers are applied recursively to nested structures, but can't
# be unapplied.

T = TypeVar("T", bound=Type)

POSITIONAL = _make_marker("Positional")
Positional = Annotated[T, POSITIONAL]
"""A type `T` can be annotated as `Positional[T]` if we want to parse it as a positional
argument."""


FIXED = _make_marker("Fixed")
Fixed = Annotated[T, FIXED]
"""A type `T` can be annotated as `Fixed[T]` to prevent `dcargs.cli` from parsing it; a
default value should be set instead. Note that fields with defaults that can't be parsed
will also be marked as fixed automatically."""

SUPPRESS = _make_marker("Suppress")
Suppress = Annotated[T, FIXED, SUPPRESS]
"""A type `T` can be annotated as `Suppress[T]` to prevent `dcargs.cli` from parsing it, and
to prevent it from showing up in helptext."""

FLAG_CONVERSION_OFF = _make_marker("FlagConversionOff")
FlagConversionOff = Annotated[T, FLAG_CONVERSION_OFF]
"""Turn off flag conversion for booleans with default values. Instead, types annotated
with `bool` will expect an explicit True or False.

Can be used directly on boolean annotations, `FlagConversionOff[bool]`, or recursively
applied to nested types."""

AVOID_SUBCOMMANDS = _make_marker("AvoidSubcommands")
AvoidSubcommands = Annotated[T, AVOID_SUBCOMMANDS]
"""Avoid creating subcommands when a default is provided for unions over nested types.
This simplifies CLI interfaces, but makes them less expressive.

Can be used directly on union types, `AvoidSubcommands[Union[...]]`, or recursively
applied to nested types."""
