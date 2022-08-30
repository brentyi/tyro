from . import extras, metadata
from ._cli import cli, generate_parser
from ._fields import MISSING_PUBLIC as MISSING
from ._instantiators import UnsupportedTypeAnnotationError

__all__ = [
    "extras",
    "metadata",
    "cli",
    "generate_parser",
    "MISSING",
    "UnsupportedTypeAnnotationError",
]

# Deprecated interface. We use a star import to prevent these from showing up in
# autocomplete engines, etc.
from ._deprecated import *  # noqa
