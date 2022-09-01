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


T = TypeVar("T", bound=Type)

FIXED = _make_marker("Fixed")
Fixed = Annotated[T, FIXED]
"""A type T can be annotated as Fixed[T] if we don't want dcargs to parse it. A default
value should be set instead."""

FLAGS_OFF = _make_marker("FlagsOff")
FlagsOff = Annotated[T, FLAGS_OFF]
"""Turn off flag conversion, which."""

SUBCOMMANDS_OFF = _make_marker("SubcommandsOff")
SubcommandsOff = Annotated[T, SUBCOMMANDS_OFF]
"""A boolean type can be annotated as NoFlag[bool] to turn off automatic flag generation."""
