"""_fmtlib is tyro's internal API for rendering ANSI-formatted text.

It's loosely inspired by `rich`, but lighter and tailored for our (more basic) needs.
"""

from __future__ import annotations

import abc
import os
import shutil
import sys
from collections import deque
from typing import Callable, Generic, Literal, TypeVar, final

from typing_extensions import ParamSpec

AnsiAttribute = Literal[
    "bold",
    "dim",
    "black",
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "white",
    "bright_black",
    "bright_red",
    "bright_green",
    "bright_yellow",
    "bright_blue",
    "bright_magenta",
    "bright_cyan",
    "bright_white",
]
_code_from_attribute: dict[AnsiAttribute, str] = {
    "bold": "1",
    "dim": "2",
    "black": "30",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "white": "37",
    "bright_black": "90",
    "bright_red": "91",
    "bright_green": "92",
    "bright_yellow": "93",
    "bright_blue": "94",
    "bright_magenta": "95",
    "bright_cyan": "96",
    "bright_white": "97",
}


# Helper function for checking if UTF-8 box drawing characters should be used.
def _should_use_utf8_drawing_chars() -> bool:
    """Check if UTF-8 box drawing characters should be used.

    Returns True if all of the following conditions are met:
    - The experimental utf8_boxes option is enabled.
    - Either stdout encoding is UTF-8 or UTF-8 boxes are forced.
    """
    from . import _settings

    return _settings._experimental_options["utf8_boxes"] and (
        sys.stdout.encoding == "utf-8" or _FORCE_UTF8_BOXES
    )


# Base classes.


class Element(abc.ABC):
    _styles: tuple[AnsiAttribute, ...] = ()

    @abc.abstractmethod
    def max_width(self) -> int: ...

    @abc.abstractmethod
    def render(self, width: int) -> list[str]: ...

    def __repr__(self) -> str:
        return "\n".join(
            self.render(
                min(self.max_width(), max(40, shutil.get_terminal_size().columns))
            )
        )


_FORCE_ANSI: bool = False


@final
class _Text(Element):
    def __init__(self, *segments: str | _Text, delimeter: str | None = None) -> None:
        if delimeter is None:
            self._segments = segments
        else:
            # Include delimeter between strings.
            segments_aug: list[str | _Text] = []
            for i in range(len(segments)):
                if i > 0:
                    segments_aug.append(delimeter)
                segments_aug.append(segments[i])
            self._segments = tuple(segments_aug)

    @staticmethod
    def get_code(styles: tuple[AnsiAttribute, ...]) -> str:
        return "\033[" + ";".join(_code_from_attribute[k] for k in styles) + "m"

    @staticmethod
    def get_reset() -> str:
        return "\033[0m"

    def __len__(self) -> int:
        return sum(map(len, self._segments))

    def max_width(self) -> int:
        return len(self)

    def as_str_no_ansi(self) -> str:
        """Return the text without any ANSI codes."""
        return "".join(
            seg if isinstance(seg, str) else seg.as_str_no_ansi()
            for seg in self._segments
        )

    def render(self, width: int | None = None) -> list[str]:
        # Render out wrappable text. We'll do this in two stages:
        # 1) Flatten segments.
        # 2) Generate list[list[tuple[str, tuple[AnsiAttribute, ...]]]], this will tell us which part / segment goes on which line.
        # 3) Generate list[list[str]], which will include the actual ANSI sequences.

        # Stage 1: recursively flatten out segments.
        stage1_out: list[tuple[str, tuple[AnsiAttribute, ...]]] = []

        def flatten(current: _Text) -> None:
            for seg in current._segments:
                if isinstance(seg, str):
                    stage1_out.append((seg, current._styles))
                else:
                    flatten(seg)

        flatten(self)

        # Stage 2: break into lines. This is actually kind of complicated.
        # Outer list is lines, inner list is segments, tuple is (text, style).
        stage2_out: list[list[tuple[str, tuple[AnsiAttribute, ...]]]] = [[]]
        stage2_current_line_counter = 0
        for text, styles in stage1_out:
            # First: break into lines.
            lines = text.split("\n")
            for line_index, line in enumerate(lines):
                # Create a new line.
                if line_index > 0:
                    stage2_out.append([])
                    stage2_current_line_counter = 0

                # Append to line one part a time.
                parts_deque: deque[str] = deque()
                parts_deque.extend(
                    part if i == 0 else f" {part}"
                    for i, part in enumerate(line.split(" "))
                )
                while len(parts_deque) > 0:
                    # While we still have parts to process:
                    # - If the part fits on the current line, add it to the current line.
                    # - Otherwise:
                    #   - If the part has a comma in it, split it by commas and continue.
                    #   - If the part is longer than a full line: we'll just blindly wrap.
                    #   - If the part has no commas, just create a new line.
                    part = parts_deque.popleft()
                    if len(stage2_out[-1]) == 0:
                        part = part.lstrip()
                    if (
                        width is None
                        or len(part) <= width - stage2_current_line_counter
                    ):
                        stage2_out[-1].append((part, styles))
                        stage2_current_line_counter += len(part)
                    elif part.find(",") not in (-1, len(part) - 1):
                        comma_index = part.index(",")
                        parts_deque.appendleft(part[comma_index + 1 :])
                        parts_deque.appendleft(part[: comma_index + 1])
                    elif len(part) > width and stage2_current_line_counter != width:
                        remaining = width - stage2_current_line_counter
                        parts_deque.extendleft([part[remaining:], part[:remaining]])
                    else:
                        # Create a new line and put the part back in the queue.
                        stage2_out.append([])
                        stage2_current_line_counter = 0
                        parts_deque.appendleft(part)

        # Stage 3: create strings including ANSI codes.
        ansi_reset = _Text.get_reset()
        stage3_out: list[list[str]] = []

        # Check experimental options for ansi_codes setting.
        from . import _settings

        enable_ansi = _settings._experimental_options["ansi_codes"] and (
            _FORCE_ANSI
            or (sys.stdout.isatty() and os.environ.get("TERM") not in (None, "dumb"))
        )

        for stage1_line in stage2_out:
            active_segment: int | None = None
            need_reset = False
            stage3_out.append([])
            used_line_length = 0
            for part, styles in stage1_line:
                ansi_part = _Text.get_code(styles)
                if styles != active_segment:
                    # Apply formatting for new segment.
                    if enable_ansi and need_reset:
                        stage3_out[-1].append(ansi_reset)
                    if enable_ansi and ansi_part is not None:
                        stage3_out[-1].append(ansi_part)
                        need_reset = True
                    else:
                        need_reset = False
                stage3_out[-1].append(part)
                used_line_length += len(part)
            if width is not None:
                stage3_out[-1].append(" " * (width - used_line_length))
            if enable_ansi and need_reset:
                stage3_out[-1].append(ansi_reset)
        return ["".join(parts) for parts in stage3_out]


@final
class _HorizontalRule(Element):
    def max_width(self) -> int:
        return 1

    def render(self, width: int) -> list[str]:
        char = "─" if _should_use_utf8_drawing_chars() else "-"
        return text[self._styles](char * width).render(width)


def _cast_element(x: Element | str) -> Element:
    if isinstance(x, str):
        return _Text(x)
    return x


@final
class _Rows(Element):
    def __init__(self, *contents: Element | str) -> None:
        self._contents = tuple(_cast_element(x) for x in contents)

    def max_width(self) -> int:
        return max(0, *(x.max_width() for x in self._contents))

    def render(self, width: int) -> list[str]:
        out = []
        for elem in self._contents:
            out.extend(elem.render(width))
        return out


@final
class _Cols(Element):
    def __init__(
        self, *contents: Element | str | tuple[Element | str, int | float | None]
    ) -> None:
        """Arguments should be type `Element` or tuples `(element, width)`.

        Widths can be either in absolute character units (integers) or as
        proportions of the container (float, 0.0-1.0)."""
        self._contents: tuple[tuple[Element, int | float | None], ...] = tuple(
            (_cast_element(c[0]), c[1])
            if isinstance(c, tuple)
            else (_cast_element(c), None)
            for c in contents
        )

    def max_width(self) -> int:
        return sum(
            (
                width if isinstance(width, int) else elem.max_width()
                for elem, width in self._contents
            ),
            0,
        )

    def render(self, width: int) -> list[str]:
        if len(self._contents) == 0:
            return []

        # Start by getting a target width for each element.
        widths: list[int] = [0] * len(self._contents)
        none_count = 0

        # First, set absolute widths.
        for i, (_, w) in enumerate(self._contents):
            if isinstance(w, int):
                widths[i] = w
            elif isinstance(w, float):
                widths[i] = int(w * width)
            else:
                none_count += 1

        # Equally allocate remaining width.
        remaining_width = width - sum(widths)
        for i, (_, w) in enumerate(self._contents):
            if w is None:
                widths[i] = max(remaining_width // none_count, 1)

        # Check if we need to adjust widths.
        total_width = sum(widths)
        if total_width != width:
            # Scale in case we're egregiously off.
            scaler = width / total_width
            for i in range(len(widths)):
                widths[i] = max(int(widths[i] * scaler + 0.5), 1)

            # Shift 1 character at a time.
            total_width = sum(widths)
            if total_width > width:
                for _ in range(total_width - width):
                    widths[widths.index(max(widths))] -= 1
                    total_width -= 1
            if total_width < width:
                for _ in range(width - total_width):
                    widths[widths.index(min(widths))] += 1
                    total_width += 1
            assert total_width == width

        # Get column lines. List indices are (columns, lines).
        column_lines: list[list[str]] = []
        for (elem, _), w in zip(self._contents, widths):
            column_lines.append(
                (_Text(elem) if isinstance(elem, str) else elem).render(w)
            )

        # Transpose column_lines. List indices are (lines, columns).
        max_line_count = max(map(len, column_lines))
        out_parts: list[list[str]] = [[] for _ in range(max_line_count)]
        for line_num in range(max_line_count):
            for i in range(len(column_lines)):
                if line_num >= len(column_lines[i]):
                    out_parts[line_num].append(" " * widths[i])
                else:
                    out_parts[line_num].append(column_lines[i][line_num])

        return ["".join(parts) for parts in out_parts]


_FORCE_UTF8_BOXES = True


@final
class _Box(Element):
    def __init__(
        self,
        title: str | _Text,
        contents: Element,
    ) -> None:
        self._title = title
        self._contents = contents

    def max_width(self) -> int:
        return self._contents.max_width() + 4

    def render(self, width: int) -> list[str]:
        out: list[str] = []
        border = text[self._styles]

        if _should_use_utf8_drawing_chars():
            top_left = "╭"
            top_right = "╮"
            bottom_left = "╰"
            bottom_right = "╯"
            horizontal = "─"
            vertical = "│"

            out.extend(
                _Text(
                    border(top_left),
                    border(horizontal),
                    " ",
                    self._title,
                    " ",
                    border(horizontal * (width - 5 - len(self._title)) + top_right),
                ).render(),
            )
            vertline = border(vertical).render()[0]
            out.extend(
                [
                    f"{vertline} {line} {vertline}"
                    for line in self._contents.render(width - 4)
                ]
            )
            out.extend(
                border(bottom_left, horizontal * (width - 2), bottom_right).render()
            )
        else:
            title_length = len(self._title)
            out.extend(
                _Text(" ", self._title, " " * (width - title_length - 1)).render()
            )
            out.extend(border(" " + "-" * (width - 2) + " ").render())
            out.extend([f"  {line}" for line in self._contents.render(width - 2)])
            out.append(" " * width)

        return out


# Subscript-based style API.

ElementParams = ParamSpec("ElementParams")
ElementT = TypeVar("ElementT", bound=Element)


class _Stylable(Generic[ElementParams, ElementT]):
    _element_type: type

    def __getitem__(
        self, attrs: AnsiAttribute | tuple[AnsiAttribute, ...]
    ) -> Callable[ElementParams, ElementT]:
        def make_stylable(
            *args: ElementParams.args, **kwargs: ElementParams.kwargs
        ) -> ElementT:
            # Create a new instance of the element type with the given styles.
            instance = self._element_type(*args, **kwargs)
            instance._styles = (
                attrs if isinstance(attrs, tuple) else (attrs,)
            ) + instance._styles
            return instance

        return make_stylable

    def __call__(
        self, *args: ElementParams.args, **kwargs: ElementParams.kwargs
    ) -> ElementT:
        return self._element_type(*args, **kwargs)


def _make_stylable(
    t: Callable[ElementParams, ElementT],
) -> _Stylable[ElementParams, ElementT]:
    class Subscripted(_Stylable):
        _element_type = t  # type: ignore

    return Subscripted()


# Public API.
text = _make_stylable(_Text)
box = _make_stylable(_Box)
rows = _make_stylable(_Rows)
cols = _make_stylable(_Cols)
hr = _make_stylable(_HorizontalRule)
