import argparse
import contextlib
import functools
import itertools
import shutil
from typing import Any, ContextManager, Generator

import termcolor
from rich.columns import Columns
from rich.console import Console, Group
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text

from . import _strings


def monkeypatch_len(obj: Any) -> int:
    if isinstance(obj, str):
        return len(_strings.strip_ansi_sequences(obj))
    else:
        return len(obj)


def dummy_termcolor_context() -> ContextManager[None]:
    """Context for turning termcolor off."""

    def dummy_colored(*args, **kwargs) -> str:
        return args[0]

    @contextlib.contextmanager
    def inner() -> Generator[None, None, None]:
        orig_colored = termcolor.colored
        termcolor.colored = dummy_colored
        yield
        termcolor.colored = orig_colored

    return inner()


def ansi_context() -> ContextManager[None]:
    """Context for working with ANSI codes + argparse:
    - Applies a temporary monkey patch for making argparse ignore ANSI codes when
      wrapping usage text.
    - Enables support for Windows via colorama.
    """

    @contextlib.contextmanager
    def inner() -> Generator[None, None, None]:
        if not hasattr(argparse, "len"):
            # Sketchy, but seems to work.
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
        max_help_position = min(24, width // 3)  # Usual is 24.

        # Try to make helptext more concise when we have a lot of fields!
        # if field_count > 16 and width >= 100:  # pragma: no cover
        #     max_help_position = min(96, width // 2)  # Usual is 24.

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
        help_width = min(60, help_width)
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

            parts.append("%*s%s\n" % (indent_first, "", help_lines[0]))  # type: ignore
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

    def _split_lines(self, text, width):
        text = self._whitespace_matcher.sub(" ", text).strip()
        return [text]
        # The textwrap module is used only for formatting help.
        # Delay its import for speeding up the common usage of argparse.
        import textwrap as textwrap

        # Sketchy, but seems to work.
        textwrap.len = monkeypatch_len  # type: ignore
        out = textwrap.wrap(text, width)
        del textwrap.len  # type: ignore
        return out

    def _fill_text(self, text, width, indent):
        return "".join(indent + line for line in text.splitlines(keepends=True))

    class _Section(object):
        def __init__(self, formatter, parent, heading=None):
            self.formatter = formatter
            self.parent = parent
            self.heading = heading
            self.items = []

        def format_help(self):
            if self.parent is None:
                return self._dcargs_format_root()
            else:
                return self._dcargs_format_nonroot()

        def _dcargs_format_root(self):
            console = Console(width=self.formatter._width)
            with console.capture() as capture:
                top_parts = []
                column_parts = []
                panel_lines_cumsum = [0]
                usage = None
                for func, args in self.items:
                    item_content = func(*args)
                    if item_content is None:
                        pass
                    elif isinstance(item_content, str):
                        top_parts.append(Text.from_ansi(item_content))
                    else:
                        # assert isinstance(item_content, Panel)
                        panel_lines_cumsum.append(
                            panel_lines_cumsum[-1]
                            + str(item_content).strip().count("\n")
                            # + 3
                        )
                        column_parts.append(item_content)

                if panel_lines_cumsum[-1] < 20:
                    print("!")
                    columns = Group(*column_parts)
                else:
                    half_lines = panel_lines_cumsum[-1] // 2
                    deltas = tuple(
                        map(
                            lambda l: l > half_lines,
                            panel_lines_cumsum,
                        )
                    ) + (True,)
                    split_index = deltas.index(True)
                    columns = Columns(
                        [
                            Group(*column_parts[:split_index]),
                            Group(*column_parts[split_index:]),
                        ],
                        column_first=True,
                        width=self.formatter._width // 2 - 2,
                    )

                console.print(Padding(Group(*top_parts), pad=(0, 2)))
                console.print(columns)
            return capture.get()

        def _dcargs_format_nonroot(self):
            # Add each child item as a rich renderable.
            item_parts = []
            has_description = False
            for func, args in self.items:
                item_content = func(*args)
                if (
                    getattr(func, "__func__", None)
                    is _ArgparseHelpFormatter._format_action
                ):
                    (action,) = args
                    assert isinstance(action, argparse.Action)
                    invocation = self.formatter._format_action_invocation(action)

                    help_position = self.formatter._max_help_position

                    # Put invocation and help side-by-side.
                    if (
                        action.help
                        and len(_strings.strip_ansi_sequences(invocation))
                        < help_position + 2
                    ):
                        table = Table(show_header=False, box=None, padding=0)
                        table.add_column(width=help_position)
                        table.add_column()
                        table.add_row(
                            Text.from_ansi(invocation), Text.from_ansi(action.help)
                        )
                        item_parts.append(table)

                    # Put invocation and help on separate lines.
                    else:
                        item_parts.append(
                            Text.from_ansi(
                                invocation + "\n",
                                style=Style(encircle=True),
                            )
                        )
                        if action.help:
                            item_parts.append(
                                Padding(
                                    Text.from_ansi(action.help),
                                    pad=(0, 0, 0, help_position),
                                )
                            )
                else:
                    assert isinstance(item_content, str)
                    if item_content.strip() != "":
                        has_description = True
                        item_parts.append(
                            Text.from_ansi(
                                item_content.strip() + "\n",
                                style=Style(dim=True),
                            )
                        )
                        item_parts.append(
                            Rule(
                                # title="item",
                                style=Style(dim=True),
                                align="left",
                            )
                        )

            if len(item_parts) == 0:
                return None

            # Get heading.
            if self.heading is not argparse.SUPPRESS and self.heading is not None:
                current_indent = self.formatter._current_indent
                heading = "%*s%s:\n" % (current_indent, "", self.heading)
            else:
                heading = ""

            # If no description: use the heading as one.
            # if not has_description:
            #     item_parts.append(
            #         Text.from_ansi(
            #             heading.strip()[:-1],
            #             style=Style(dim=True),
            #         )
            #     )
            #     item_parts.append(
            #         Rule(
            #             # title="test",
            #             style=Style(dim=True),
            #             align="left",
            #         )
            #     )
            # item_parts = item_parts[-2:] + item_parts[:-2]

            # return Group(*item_parts)
            if not has_description:
                return Panel(
                    Group(*item_parts),
                    title=heading.strip()[:-1],
                    title_align="left",
                    border_style=Style(dim=True),
                    padding=(1, 1, 0, 1),
                )
            else:
                return Panel(
                    Group(*item_parts),
                    # title=heading,
                    # title_align="left",
                    border_style=Style(dim=True),
                )

            # # format the indented section
            # if self.parent is not None:
            #     self.formatter._indent()
            # join = self.formatter._join_parts
            # item_help = join([func(*args) for func, args in self.items])
            # if self.parent is not None:
            #     self.formatter._dedent()
            #
            # # return nothing if the section was empty
            # if not item_help:
            #     return ''
            #
            # # add the heading if the section was non-empty
            # if self.heading is not SUPPRESS and self.heading is not None:
            #     current_indent = self.formatter._current_indent
            #     heading = '%*s%s:\n' % (current_indent, '', self.heading)
            # else:
            #     heading = ''
            #
            # # join the section-initial newline, the heading and the help
            # return join(['\n', heading, item_help, '\n'])
