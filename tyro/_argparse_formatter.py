"""Utilities and functions for helptext formatting. We replace argparse's simple help
messages with ones that:
    - Are more nicely formatted!
    - Support multiple columns when many fields are defined.
    - Use `rich` for formatting.
    - Can be themed with an accent color.

This is largely built by fussing around in argparse implementation details, and is by
far the hackiest part of `tyro`.
"""
import argparse
import contextlib
import dataclasses
import itertools
import shutil
from typing import Any, ContextManager, Generator, List, Optional

from rich.columns import Columns
from rich.console import Console, Group, RenderableType
from rich.padding import Padding
from rich.panel import Panel
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from . import _arguments, _strings


@dataclasses.dataclass
class TyroTheme:
    border: Style = Style()
    description: Style = Style()
    invocation: Style = Style()
    metavar: Style = Style()
    metavar_fixed: Style = Style()
    helptext: Style = Style()
    helptext_required: Style = Style()
    helptext_default: Style = Style()

    def as_rich_theme(self) -> Theme:
        return Theme(vars(self))


def set_accent_color(accent_color: Optional[str]) -> None:
    """Set an accent color to use in help messages. Takes any color supported by `rich`,
    see `python -m rich.color`. Experimental."""
    THEME.border = Style(color=accent_color, dim=True)
    THEME.description = Style(color=accent_color, bold=True)
    THEME.invocation = Style()
    THEME.metavar = Style(color=accent_color, bold=True)
    THEME.metavar_fixed = Style(color="red", bold=True)
    THEME.helptext = Style(dim=True)
    THEME.helptext_required = Style(color="bright_red", bold=True)
    THEME.helptext_default = Style(
        color="cyan"
        if accent_color != "cyan"
        else "magenta"
        # Another option: make default color match accent color. This is maybe more
        # visually consistent, but harder to read.
        # color=accent_color if accent_color is not None else "cyan",
        # dim=accent_color is not None,
    )


# TODO: this is a prototype; for a v1.0.0 release we should revisit whether the global
# state here is acceptable or not.
THEME = TyroTheme()
set_accent_color(None)


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


def str_from_rich(
    renderable: RenderableType, width: Optional[int] = None, soft_wrap: bool = False
) -> str:
    console = Console(width=width, theme=THEME.as_rich_theme())
    with console.capture() as out:
        console.print(renderable, soft_wrap=soft_wrap)
    return out.get().rstrip("\n")


class TyroArgparseHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def __init__(self, prog: str):
        indent_increment = 4
        width = shutil.get_terminal_size().columns - 2
        max_help_position = 24
        self._fixed_help_position = False

        # TODO: hacky. Refactor this.
        self._strip_ansi_sequences = not _arguments.USE_RICH

        super().__init__(prog, indent_increment, max_help_position, width)

    def _format_args(self, action, default_metavar):
        """Override _format_args() to ignore nargs and always expect single string
        metavars."""
        get_metavar = self._metavar_formatter(action, default_metavar)

        out = get_metavar(1)[0]
        if isinstance(out, str):
            # Can result in an failed argparse assertion if we turn off soft wrapping.
            return (
                out
                if self._strip_ansi_sequences
                else str_from_rich(
                    Text.from_ansi(
                        out,
                        style=THEME.metavar_fixed
                        if out == "{fixed}"
                        else THEME.metavar,
                    ),
                    soft_wrap=True,
                )
            )
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

    def format_help(self):
        # Try with and without a fixed help position, then return the shorter help
        # message.
        # For dense multi-column layouts, the fixed help position is often shorter.
        # For wider layouts, using the default help position settings can be more
        # efficient.
        self._tyro_rule = None
        self._fixed_help_position = False
        help1 = super().format_help()

        self._tyro_rule = None
        self._fixed_help_position = True
        help2 = super().format_help()

        out = help1 if help1.count("\n") < help2.count("\n") else help2

        if self._strip_ansi_sequences:
            return _strings.strip_ansi_sequences(out)
        else:
            return out

    class _Section(object):
        def __init__(self, formatter, parent, heading=None):
            self.formatter = formatter
            self.parent = parent
            self.heading = heading
            self.items = []
            self.formatter._tyro_rule = None

        def format_help(self):
            if self.parent is None:
                return self._tyro_format_root()
            else:
                return self._tyro_format_nonroot()

        def _tyro_format_root(self):
            console = Console(width=self.formatter._width, theme=THEME.as_rich_theme())
            with console.capture() as capture:
                # Get rich renderables from items.
                top_parts = []
                column_parts = []
                column_parts_lines = []
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
                        column_parts.append(item_content)
                        # Estimate line count. This won't correctly account for
                        # wrapping, as we don't know the column layout yet.
                        column_parts_lines.append(
                            str_from_rich(item_content, width=65).strip().count("\n")
                            + 1
                        )

                # Split into columns.
                min_column_width = 65
                height_breakpoint = 50
                column_count = max(
                    1,
                    min(
                        sum(column_parts_lines) // height_breakpoint + 1,
                        self.formatter._width // min_column_width,
                        len(column_parts),
                    ),
                )
                if column_count > 1:
                    column_width = self.formatter._width // column_count - 1
                    # Correct the line count for each panel using the known column
                    # width. This will account for word wrap.
                    column_parts_lines = map(
                        lambda p: str_from_rich(p, width=column_width)
                        .strip()
                        .count("\n")
                        + 1,
                        column_parts,
                    )
                else:
                    column_width = None

                column_lines = [0 for i in range(column_count)]
                column_parts_grouped = [[] for i in range(column_count)]
                for p, l in zip(column_parts, column_parts_lines):
                    chosen_column = column_lines.index(min(column_lines))
                    column_parts_grouped[chosen_column].append(p)
                    column_lines[chosen_column] += l
                columns = Columns(
                    [Group(*g) for g in column_parts_grouped],
                    column_first=True,
                    width=column_width,
                )

                console.print(Group(*top_parts))
                console.print(columns)
            return capture.get()

        def _format_action(self, action: argparse.Action):
            invocation = self.formatter._format_action_invocation(action)
            indent = self.formatter._current_indent
            help_position = min(
                self.formatter._action_max_length + 4 + indent,
                self.formatter._max_help_position,
            )
            if self.formatter._fixed_help_position:
                help_position = 4

            item_parts: List[RenderableType] = []

            # Put invocation and help side-by-side.
            if action.option_strings == ["-h", "--help"]:
                # Darken helptext for --help flag. This makes it visually consistent
                # with the helptext strings defined via docstrings and set by
                # _arguments.py.
                assert action.help is not None
                action.help = str_from_rich(
                    Text.from_markup("[helptext]" + action.help + "[/helptext]")
                )

            # Unescape % signs, which need special handling in argparse.
            if action.help is not None:
                assert isinstance(action.help, str)
                helptext = (
                    Text.from_ansi(action.help.replace("%%", "%"))
                    if _strings.strip_ansi_sequences(action.help) != action.help
                    else Text.from_markup(action.help.replace("%%", "%"))
                )
            else:
                helptext = Text("")

            if (
                action.help
                and len(_strings.strip_ansi_sequences(invocation)) < help_position - 1
                and not self.formatter._fixed_help_position
            ):
                table = Table(show_header=False, box=None, padding=0)
                table.add_column(width=help_position - indent)
                table.add_column()
                table.add_row(
                    Text.from_ansi(
                        invocation,
                        style=THEME.invocation,
                    ),
                    helptext,
                )
                item_parts.append(table)

            # Put invocation and help on separate lines.
            else:
                item_parts.append(
                    Text.from_ansi(
                        invocation + "\n",
                        style=THEME.invocation,
                    )
                )
                if action.help:
                    item_parts.append(
                        Padding(
                            # Unescape % signs, which need special handling in argparse.
                            helptext,
                            pad=(0, 0, 0, help_position),
                        )
                    )

            # Add subactions, indented.
            try:
                subaction: argparse.Action
                for subaction in action._get_subactions():  # type: ignore
                    self.formatter._indent()
                    item_parts.append(
                        Padding(
                            Group(*self._format_action(subaction)),
                            pad=(0, 0, 0, self.formatter._indent_increment),
                        )
                    )
                    self.formatter._dedent()
            except AttributeError:
                pass

            return item_parts

        def _tyro_format_nonroot(self):
            # Add each child item as a rich renderable.
            description_part = None
            item_parts = []
            for func, args in self.items:
                item_content = func(*args)
                if (
                    getattr(func, "__func__", None)
                    is TyroArgparseHelpFormatter._format_action
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
                            item_content.strip() + "\n",
                            style=THEME.description,
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

            # Determine width for divider below description text. This is shared across
            # all sections in a particular formatter.
            lines = list(
                itertools.chain(
                    *map(
                        lambda p: _strings.strip_ansi_sequences(
                            str_from_rich(
                                p, width=self.formatter._width, soft_wrap=True
                            )
                        )
                        .rstrip()
                        .split("\n"),
                        item_parts + [description_part]
                        if description_part is not None
                        else item_parts,
                    )
                )
            )
            max_width = max(map(len, lines))

            if self.formatter._tyro_rule is None:
                # Note: we don't use rich.rule.Rule() because this will make all of
                # the panels expand to fill the full width of the console. (this only
                # impacts single-column layouts)
                self.formatter._tyro_rule = Text.from_ansi(
                    "─" * max_width, style=THEME.border, overflow="crop"
                )
            elif len(self.formatter._tyro_rule._text[0]) < max_width:
                self.formatter._tyro_rule._text = ["─" * max_width]

            # Add description text if needed.
            if description_part is not None:
                item_parts = [
                    description_part,
                    self.formatter._tyro_rule,
                ] + item_parts

            return Panel(
                Group(*item_parts),
                title=heading,
                title_align="left",
                border_style=THEME.border,
                # padding=(1, 1, 0, 1),
            )
