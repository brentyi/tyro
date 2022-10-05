from typing import TYPE_CHECKING, Type, TypeVar

from typing_extensions import Annotated

from .. import _singleton

# Current design issue: markers are applied recursively to nested structures, but can't
# be unapplied.

# Note that all Annotated[T, None] values are just for static checkers. The real marker
# singletons are instantiated dynamically below.
#
# An alias could ideally be made, but SpecialForm aliases are not well supported by static analysis tools.

T = TypeVar("T", bound=Type)

Positional = Annotated[T, None]
"""A type `T` can be annotated as `Positional[T]` if we want to parse it as a positional
argument."""

Fixed = Annotated[T, None]
"""A type `T` can be annotated as `Fixed[T]` to prevent `tyro.cli` from parsing it; a
default value should be set instead. Note that fields with defaults that can't be parsed
will also be marked as fixed automatically."""

Suppress = Annotated[T, None]
"""A type `T` can be annotated as `Suppress[T]` to prevent `tyro.cli` from parsing it, and
to prevent it from showing up in helptext."""

SuppressFixed = Annotated[T, None]
"""Hide fields that are either manually or automatically marked as fixed."""

FlagConversionOff = Annotated[T, None]
"""Turn off flag conversion for booleans with default values. Instead, types annotated
with `bool` will expect an explicit True or False.

Can be used directly on boolean annotations, `FlagConversionOff[bool]`, or recursively
applied to nested types."""

AvoidSubcommands = Annotated[T, None]
"""Avoid creating subcommands when a default is provided for unions over nested types.
This simplifies CLI interfaces, but makes them less expressive.

Can be used directly on union types, `AvoidSubcommands[Union[...]]`, or recursively
applied to nested types."""

OmitSubcommandPrefixes = Annotated[T, None]
"""Make flags used for keyword arguments in subcommands shorter by omitting prefixes.

If we have a structure with the field:

    cmd: Union[Commit, Checkout]

By default, --cmd.branch may be generated as a flag for each dataclass in the union.
If subcommand prefixes are omitted, we would instead simply have --branch.
"""


# Dynamically generate marker singletons.
# These can be used one of two ways:
# - Marker[T]
# - Annotated[T, Marker]
class Marker(_singleton.Singleton):
    def __getitem__(self, key):
        return Annotated.__class_getitem__((key, self))  # type: ignore


if not TYPE_CHECKING:

    def _make_marker(description: str) -> Marker:
        class _InnerMarker(Marker):
            def __repr__(self):
                return description

        return _InnerMarker()

    _dynamic_marker_types = {}
    for k, v in dict(globals()).items():
        if v == Annotated[T, None]:
            _dynamic_marker_types[k] = _make_marker(k)
    globals().update(_dynamic_marker_types)
    del _dynamic_marker_types
