"""Backend implementations for parsing command-line arguments.

`TyroBackend` is faster and more flexible, and should be used by default. We
don't have a public API for switching to the ArgparseBackend.
"""

from ._argparse_backend import ArgparseBackend as ArgparseBackend
from ._tyro_backend import TyroBackend as TyroBackend
