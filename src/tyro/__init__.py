from typing import TYPE_CHECKING

from . import conf as conf
from . import constructors as constructors
from . import extras as extras
from ._cli import cli as cli
from ._singleton import MISSING as MISSING

# Deprecated interface.
if not TYPE_CHECKING:
    from ._deprecated import *  # noqa
    from .constructors._primitive_spec import (
        UnsupportedTypeAnnotationError as UnsupportedTypeAnnotationError,
    )


# TODO: this should be synchronized automatically with the pyproject.toml.
__version__ = "0.8.14"
