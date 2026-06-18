from typing import TYPE_CHECKING

__version__ = "1.0.13"


from . import conf as conf
from . import constructors as constructors
from ._cli import cli as cli
from ._settings import _experimental_options as _experimental_options
from ._singleton import MISSING as MISSING
from ._singleton import MISSING_NONPROP as MISSING_NONPROP

if TYPE_CHECKING:
    from . import extras as extras

# Deprecated interface.
if not TYPE_CHECKING:
    from .constructors._primitive_spec import (
        UnsupportedTypeAnnotationError as UnsupportedTypeAnnotationError,
    )

_DEPRECATED_LAZY = {
    "parse": ("._cli", "cli"),
    "from_yaml": (".extras._serialization", "from_yaml"),
    "to_yaml": (".extras._serialization", "to_yaml"),
}


def __getattr__(name: str):
    if name == "extras":
        import importlib

        extras = importlib.import_module(".extras", __name__)
        globals()["extras"] = extras
        return extras
    if name in _DEPRECATED_LAZY:
        import importlib

        module_path, attr = _DEPRECATED_LAZY[name]
        mod = importlib.import_module(module_path, __name__)
        val = getattr(mod, attr)
        globals()[name] = val
        return val
    raise AttributeError(f"module 'tyro' has no attribute {name!r}")
