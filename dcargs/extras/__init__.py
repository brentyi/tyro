"""The :mod:`dcargs.extras` submodule contains helpers that complement :func:`dcargs.cli()`, but
aren't considered part of the core interface."""

from ._base_configs import subcommand_type_from_defaults
from ._serialization import from_yaml, to_yaml

__all__ = ["subcommand_type_from_defaults", "to_yaml", "from_yaml"]
