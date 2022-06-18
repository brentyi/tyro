from ._cli import cli
from ._instantiators import UnsupportedTypeAnnotationError
from ._serialization import from_yaml, to_yaml

__all__ = [
    "UnsupportedTypeAnnotationError",
    "cli",
    "from_yaml",
    "to_yaml",
]

from typing import TYPE_CHECKING

if not TYPE_CHECKING:

    def parse(*args, **kwargs):
        # API breaking transition plan:
        # (v0.1.0) Rename dcargs.parse() to dcargs.cli(). Keep the former as an alias.
        # (      ) Enable deprecation warning.
        # (      ) Remove dcargs.parse() alias.
        #
        # import warnings
        #
        # warnings.warn(
        #     "`dcargs.parse()` has been renamed `dcargs.cli()`. It will be removed"
        #     " soon.",
        #     DeprecationWarning,
        #     stacklevel=2,
        # )
        return cli(*args, **kwargs)
