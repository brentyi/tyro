from typing import Literal

from . import _fmtlib as fmt

# TODO: revisit global.
ACCENT_COLOR: fmt.AnsiAttribute = "white"


def set_accent_color(
    accent_color: Literal[
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
    | None,
) -> None:
    """Set an accent color to use in help messages. Experimental."""
    global ACCENT_COLOR
    ACCENT_COLOR = accent_color if accent_color is not None else "white"
