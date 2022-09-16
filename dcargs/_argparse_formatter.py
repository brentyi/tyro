import argparse
import contextlib
import functools
import re as _re
import shutil
from typing import Any, ContextManager, Generator, List

import termcolor
from rich.columns import Columns
from rich.console import Console, Group, RenderableType
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text

from . import _strings

BORDER_STYLE = Style(color="bright_blue", dim=True)
DESCRIPTION_STYLE = Style(color="bright_blue", bold=True)
INVOCATION_STYLE = Style(color="bright_white", bold=True)
METAVAR_STYLE = Style(color="bright_blue")


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


def str_from_rich(renderable: RenderableType) -> str:
    console = Console()
    with console.capture() as out:
        console.print(renderable, soft_wrap=True)
    return out.get().rstrip("\n")


def make_formatter_class(field_count: int) -> Any:
    return functools.partial(_ArgparseHelpFormatter, field_count=field_count)


class _ArgparseHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def __init__(self, prog, *, field_count: int):
        indent_increment = 2
        width = shutil.get_terminal_size().columns - 2

        # Try to make helptext more concise when we have a lot of fields!
        if field_count > 16 and width >= 100:  # pragma: no cover
            max_help_position = min(12, width // 2)  # Usual is 24.
        else:
            max_help_position = min(24, width // 3)  # Usual is 24.

        super().__init__(prog, indent_increment, max_help_position, width)

    def _format_args(self, action, default_metavar):
        """Override _format_args() to ignore nargs and always expect single string
        metavars."""
        get_metavar = self._metavar_formatter(action, default_metavar)

        out = get_metavar(1)[0]
        if isinstance(out, str):
            return str_from_rich(Text(out, style=METAVAR_STYLE))
        return out

    def add_argument(self, action):  # pragma: no cover
        # Patch to avoid super long arguments from shifting the helptext of all of the
        # fields.
        prev_max_length = self._action_max_length
        super().add_argument(action)
        if self._action_max_length > self._max_help_position + 2:
            self._action_max_length = prev_max_length

    def _split_lines(self, text, width):
        text = self._whitespace_matcher.sub(" ", text).strip()
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
                # Get rich renderables from items.
                top_parts = []
                column_parts = []
                panel_lines_cumsum = [0]
                for func, args in self.items:
                    item_content = func(*args)
                    if item_content is None:
                        pass

                    # Add strings. (usage, description, etc)
                    elif isinstance(item_content, str):
                        if item_content.strip() == "":
                            continue
                        top_parts.append(Text.from_ansi(item_content))

                    # Add panels. (argument groups, subcommands, etc)
                    else:
                        assert isinstance(item_content, Panel)
                        with console.capture() as length_capture:
                            console.print(item_content)
                        panel_lines_cumsum.append(
                            panel_lines_cumsum[-1]
                            + length_capture.get().strip().count("\n")
                            + 2
                        )
                        column_parts.append(item_content)

                def _index_closest_to(line_count):
                    """Find the index of the first panel where the line count is closest
                    to a target length."""
                    deltas = tuple(
                        map(lambda l: abs(l - line_count), panel_lines_cumsum)
                    )
                    return deltas.index(min(deltas))

                # Single column.
                if panel_lines_cumsum[-1] < 40 or self.formatter._width < 160:
                    # Wrapping in columns here prevents everything from going
                    # full-width.
                    columns = Columns([Group(*column_parts)], column_first=True)

                # Two column mode.
                elif panel_lines_cumsum[-1] < 120 or self.formatter._width < 205:
                    split_index = _index_closest_to(panel_lines_cumsum[-1] // 2)
                    column_width = self.formatter._width // 2 - 1
                    columns = Columns(
                        [
                            Group(*column_parts[:split_index]),
                            Group(*column_parts[split_index:]),
                        ],
                        column_first=True,
                        width=column_width,
                    )

                # Three column mode.
                else:
                    split_index1 = _index_closest_to(panel_lines_cumsum[-1] // 3)
                    split_index2 = _index_closest_to(
                        panel_lines_cumsum[split_index1] + panel_lines_cumsum[-1] // 3
                    )
                    column_width = self.formatter._width // 3 - 1
                    columns = Columns(
                        [
                            Group(*column_parts[:split_index1]),
                            Group(*column_parts[split_index1:split_index2]),
                            Group(*column_parts[split_index2:]),
                        ],
                        column_first=True,
                        width=column_width,
                    )

                # Three column mode.

                console.print(Group(*top_parts))
                console.print(columns)
            return capture.get()

        def _format_action(self, action: argparse.Action):
            invocation = self.formatter._format_action_invocation(action)
            help_position = self.formatter._action_max_length

            item_parts: List[RenderableType] = []

            # Put invocation and help side-by-side.
            if (
                action.help
                and len(_strings.strip_ansi_sequences(invocation)) < help_position - 1
            ):
                table = Table(show_header=False, box=None, padding=0)
                table.add_column(width=help_position)
                table.add_column()
                table.add_row(
                    Text.from_ansi(
                        invocation,
                        style=INVOCATION_STYLE,
                    ),
                    # Unescape % signs, which need special handling in argparse.
                    Text.from_ansi(action.help.replace("%%", "%")),
                )
                item_parts.append(table)

            # Put invocation and help on separate lines.
            else:
                item_parts.append(
                    Text.from_ansi(
                        invocation + "\n",
                        style=INVOCATION_STYLE,
                    )
                )
                if action.help:
                    item_parts.append(
                        Padding(
                            # Unescape % signs, which need special handling in argparse.
                            Text.from_ansi(action.help.replace("%%", "%")),
                            pad=(0, 0, 0, help_position),
                        )
                    )

            # Add subactions, indented.
            try:
                subaction: argparse.Action
                for subaction in action._get_subactions():  # type: ignore
                    item_parts.append(
                        Padding(
                            Group(*self._format_action(subaction)), pad=(0, 0, 0, 4)
                        )
                    )
            except AttributeError:
                pass

            return item_parts

        def _dcargs_format_nonroot(self):
            # Add each child item as a rich renderable.
            description_part = None
            item_parts = []
            for func, args in self.items:
                item_content = func(*args)
                if (
                    getattr(func, "__func__", None)
                    is _ArgparseHelpFormatter._format_action
                ):
                    (action,) = args
                    assert isinstance(action, argparse.Action)
                    item_parts.extend(self._format_action(action))

                else:
                    assert isinstance(item_content, str)
                    if item_content.strip() != "":
                        assert (
                            description_part is None
                        )  # Should only have one description part.
                        description_part = Text.from_ansi(
                            " " + item_content.strip() + "\n",
                            style=DESCRIPTION_STYLE,
                        )

            if len(item_parts) == 0:
                return None

            # Get heading.
            if self.heading is not argparse.SUPPRESS and self.heading is not None:
                current_indent = self.formatter._current_indent
                heading = "%*s%s:\n" % (current_indent, "", self.heading)
                # Remove colon from heading.
                heading = heading.strip()[:-1]
            else:
                heading = ""

            if description_part is not None:
                item_parts = [description_part, Rule(style=BORDER_STYLE)] + item_parts

            return Panel(
                Group(*item_parts),
                title=heading,
                title_align="left",
                border_style=BORDER_STYLE,
                # padding=(1, 1, 0, 1),
            )

    def _format_actions_usage(self, actions, groups):
        # find group indices and identify actions in groups
        group_actions = set()
        inserts = {}
        for group in groups:
            try:
                start = actions.index(group._group_actions[0])  # type: ignore
            except ValueError:
                continue
            else:
                end = start + len(group._group_actions)
                if actions[start:end] == group._group_actions:  # type: ignore
                    for action in group._group_actions:
                        group_actions.add(action)
                    if not group.required:  # type: ignore
                        if start in inserts:
                            inserts[start] += " ["
                        else:
                            inserts[start] = "["
                        if end in inserts:
                            inserts[end] += "]"
                        else:
                            inserts[end] = "]"
                    else:
                        if start in inserts:
                            inserts[start] += " ("
                        else:
                            inserts[start] = "("
                        if end in inserts:
                            inserts[end] += ")"
                        else:
                            inserts[end] = ")"
                    for i in range(start + 1, end):
                        inserts[i] = "|"

        # collect all actions format strings
        parts = []
        for i, action in enumerate(actions):
            # suppressed arguments are marked with None
            # remove | separators for suppressed arguments
            if action.help is argparse.SUPPRESS:
                parts.append(None)
                if inserts.get(i) == "|":
                    inserts.pop(i)
                elif inserts.get(i + 1) == "|":
                    inserts.pop(i + 1)

            # produce all arg strings
            elif not action.option_strings:
                default = self._get_default_metavar_for_positional(action)
                part = self._format_args(action, default)

                # if it's in a group, strip the outer []
                if action in group_actions:
                    if part[0] == "[" and part[-1] == "]":
                        part = part[1:-1]

                # add the action string to the list
                parts.append(part)

            # produce the first way to invoke the option in brackets
            else:
                option_string = action.option_strings[0]

                # if the Optional doesn't take a value, format is:
                #    -s or --long
                if action.nargs == 0:
                    part = "%s" % option_string

                # if the Optional takes a value, format is:
                #    -s ARGS or --long ARGS
                else:
                    default = self._get_default_metavar_for_optional(action)
                    args_string = self._format_args(action, default)
                    part = "%s %s" % (option_string, args_string)

                # make it look optional if it's not required or in a group
                if not action.required and action not in group_actions:
                    part = "[%s]" % part

                # Apply invocation style.
                part = str_from_rich(Text(part, style=INVOCATION_STYLE))

                # add the action string to the list
                parts.append(part)

        # insert things at the necessary indices
        for i in sorted(inserts, reverse=True):
            parts[i:i] = [inserts[i]]

        # join all the action items with spaces
        text = " ".join([item for item in parts if item is not None])

        # clean up separators for mutually exclusive groups
        open = r"[\[(]"
        close = r"[\])]"
        text = _re.sub(r"(%s) " % open, r"\1", text)
        text = _re.sub(r" (%s)" % close, r"\1", text)
        text = _re.sub(r"%s *%s" % (open, close), r"", text)
        text = _re.sub(r"\(([^|]*)\)", r"\1", text)
        text = text.strip()

        # return the text
        return text
