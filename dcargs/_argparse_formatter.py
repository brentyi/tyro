import argparse
import contextlib
import functools
import itertools
import shutil
from typing import Any, ContextManager, Generator

from . import _strings


def monkeypatch_len(obj: Any) -> int:
    if isinstance(obj, str):
        return len(_strings.strip_ansi_sequences(obj))
    else:
        return len(obj)


def ansi_context() -> ContextManager[None]:
    """Context for working with ANSI codes + argparse:
    - Applies a temporary monkey patch for making argparse ignore ANSI codes when
      wrapping usage text.
    - Enables support for Windows via colorama.
    """

    @contextlib.contextmanager
    def inner() -> Generator[None, None, None]:
        if not hasattr(argparse, "len"):
            argparse.len = monkeypatch_len  # type: ignore
            try:
                # Use Colorama to support coloring in Windows shells.
                import colorama  # type: ignore

                # Notes:
                #
                # (1) This context manager looks very nice and local, but under-the-hood
                # does some global operations which look likely to cause unexpected
                # behavior if another library relies on `colorama.init()` and
                # `colorama.deinit()`.
                #
                # (2) SSHed into a non-Windows machine from a WinAPI terminal => this
                # won't work.
                #
                # Fixing these issues doesn't seem worth it: it doesn't seem like there
                # are low-effort solutions for either problem, and more modern terminals
                # in Windows (PowerShell, MSYS2, ...) do support ANSI codes anyways.
                with colorama.colorama_text():
                    yield

            except ImportError:
                yield

            del argparse.len  # type: ignore
        else:
            # No-op when the context manager is nested.
            yield

    return inner()


def make_formatter_class(field_count: int) -> Any:
    return functools.partial(_ArgparseHelpFormatter, field_count=field_count)


class _ArgparseHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def __init__(self, prog, *, field_count: int):
        indent_increment = 2
        width = shutil.get_terminal_size().columns - 2
        max_help_position = min(36, width // 3)  # Usual is 24.

        # Try to make helptext more concise when we have a lot of fields!
        if field_count > 16 and width >= 100:  # pragma: no cover
            max_help_position = min(96, width // 2)  # Usual is 24.

        super().__init__(prog, indent_increment, max_help_position, width)

    def _format_args(self, action, default_metavar):
        """Override _format_args() to ignore nargs and always expect single string
        metavars."""
        get_metavar = self._metavar_formatter(action, default_metavar)
        return get_metavar(1)[0]

    def add_argument(self, action):  # pragma: no cover
        # Patch to avoid super long arguments from shifting the helptext of all of the
        # fields.
        prev_max_length = self._action_max_length
        super().add_argument(action)
        if (
            self._action_max_length >= 40
            and self._action_max_length > self._max_help_position + 2
        ):
            self._action_max_length = prev_max_length

    def _format_action(self, action):
        # determine the required width and the entry label
        help_position = min(self._action_max_length + 2, self._max_help_position)
        help_width = max(self._width - help_position, 11)
        action_width = help_position - self._current_indent - 2
        action_header = self._format_action_invocation(action)

        # no help; start on same line and add a final newline
        if not action.help:
            tup = self._current_indent, "", action_header
            action_header = "%*s%s\n" % tup

        # short action name; start on the same line and pad two spaces
        elif monkeypatch_len(action_header) <= action_width:
            # Original:
            # tup = self._current_indent, "", action_width, action_header
            # action_header = "%*s%-*s  " % tup
            # <new>
            action_header = (
                " " * self._current_indent
                + action_header
                + " " * (action_width - monkeypatch_len(action_header) + 2)
            )
            # </new>
            indent_first = 0

        # long action name; start on the next line
        else:
            tup = self._current_indent, "", action_header
            action_header = "%*s%s\n" % tup
            indent_first = help_position

        # collect the pieces of the action help
        parts = [action_header]

        # if there was help for the action, add lines of help text
        if action.help:
            help_text = self._expand_help(action)
            # <new>
            # Respect existing line breaks.
            help_lines = tuple(
                itertools.chain(
                    *(self._split_lines(h, help_width) for h in help_text.split("\n"))
                )
            )
            # </new>
            parts.append("%*s%s\n" % (indent_first, "", help_lines[0]))
            for line in help_lines[1:]:
                parts.append("%*s%s\n" % (help_position, "", line))

        # or add a newline if the description doesn't end with one
        elif not action_header.endswith("\n"):
            parts.append("\n")

        # if there are any sub-actions, add their help as well
        for subaction in self._iter_indented_subactions(action):
            parts.append(self._format_action(subaction))

        # return a single string
        return self._join_parts(parts)
