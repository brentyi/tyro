import argparse
import contextlib
from typing import Any

from . import _strings


@contextlib.contextmanager
def argparse_ansi_monkey_patch():
    """Temporary monkey patch for making argparse ignore ANSI codes when wrapping usage
    text."""

    def monkeypatched_len(obj: Any) -> int:
        if isinstance(obj, str):
            return len(_strings.strip_ansi_sequences(obj))
        else:
            return len(obj)

    argparse.len = monkeypatched_len  # type: ignore
    yield
    del argparse.len  # type: ignore


class ArgparseHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def _format_args(self, action, default_metavar):
        """Override _format_args() to ignore nargs and always expect single string
        metavars."""
        get_metavar = self._metavar_formatter(action, default_metavar)
        return get_metavar(1)[0]
