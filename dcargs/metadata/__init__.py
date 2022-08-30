"""The :mod:`dcargs.metadata` submodule contains helpers for attaching parsing-specific
metadata to types. For the forseeable future, this is limited to subcommand configuration.

Features here are supported, but generally contradict the core design ethos of
:func:`dcargs.cli()`.

As such:
1. Usage of existing functionality should be avoided unless absolutely necessary.
2. Introduction of new functionality should be avoided unless it (a) cannot be
   reproduced with standard type annotations and (b) meaningfully improves the
   usefulness of the library.
"""

from ._subcommands import subcommand

__all__ = ["subcommand"]
