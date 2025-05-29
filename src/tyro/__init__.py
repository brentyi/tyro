from typing import TYPE_CHECKING

__version__ = "0.9.22"


from . import conf as conf
from . import constructors as constructors
from . import extras as extras
from ._cli import cli as cli
from ._singleton import MISSING as MISSING
from .constructors import LazyAnnotation as LazyAnnotation

# Deprecated interface.
if not TYPE_CHECKING:
    from ._deprecated import *  # noqa
    from .constructors._primitive_spec import (
        UnsupportedTypeAnnotationError as UnsupportedTypeAnnotationError,
    )
