from typing import TYPE_CHECKING

__version__ = "0.10.0a5"


from . import conf as conf
from . import constructors as constructors
from . import extras as extras
from ._cli import cli as cli
from ._settings import _experimental_options as _experimental_options
from ._singleton import MISSING as MISSING
from ._singleton import MISSING_NONPROP as MISSING_NONPROP

# Deprecated interface.
if not TYPE_CHECKING:
    from ._deprecated import *  # noqa
    from .constructors._primitive_spec import (
        UnsupportedTypeAnnotationError as UnsupportedTypeAnnotationError,
    )
