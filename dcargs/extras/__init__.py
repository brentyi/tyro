"""The :mod:`dcargs.extras` submodule contains helpers that complement :func:`dcargs.cli()`, but
aren't considered part of the core interface."""

from ._base_configs import subcommand_union_from_mapping
from ._serialization import from_yaml, to_yaml

__all__ = ["subcommand_union_from_mapping", "to_yaml", "from_yaml"]
