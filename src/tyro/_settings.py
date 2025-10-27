"""Experimental features and settings for tyro.

This module contains experimental features and settings that may change or be removed
in future versions. Use with caution in production code.

Note: _experimental_options is exported in tyro.__init__ and should be accessed as:
  tyro._experimental_options
"""

from __future__ import annotations

import contextlib
import os
import sys
import time
from typing import Any, Literal

from typing_extensions import TypedDict

from . import _fmtlib as fmt


class ExperimentalOptionsDict(TypedDict):
    """Options for experimental tyro features.

    Attributes:
        enable_timing: Enable timing output for performance benchmarking.
        backend: Backend to use for parsing ("argparse" or "tyro").
        utf8_boxes: Enable UTF-8 box drawing characters in formatted output.
        ansi_codes: Enable ANSI color codes in formatted output.
    """

    enable_timing: bool
    backend: Literal["argparse", "tyro"]
    utf8_boxes: bool
    ansi_codes: bool


@contextlib.contextmanager
def timing_context(name: str):
    """Context manager to time a block of code."""
    if not _experimental_options["enable_timing"]:
        yield
        return

    start_time = time.perf_counter()
    yield
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    print(f"{name} took {elapsed_time:.4f} seconds", file=sys.stderr, flush=True)


def _read_option(str_name: str, typ: Any, default: Any) -> Any:  # pragma: no cover
    if str_name in os.environ:
        from .constructors import (
            ConstructorRegistry,
            PrimitiveTypeInfo,
            UnsupportedTypeAnnotationError,
        )

        spec = ConstructorRegistry.get_primitive_spec(
            PrimitiveTypeInfo.make(typ, set())
        )
        assert not isinstance(spec, UnsupportedTypeAnnotationError)
        value = os.environ[str_name]
        if spec.choices is not None:
            assert value in spec.choices, (
                f"{str_name}={value} not in choices {spec.choices}"
            )
        return spec.instance_from_str([value])
    return default


# Global experimental options dictionary.
_experimental_options: ExperimentalOptionsDict = {
    "enable_timing": _read_option("PYTHON_TYRO_ENABLE_TIMING", bool, False),
    "backend": _read_option("PYTHON_TYRO_BACKEND", Literal["argparse", "tyro"], "tyro"),
    "utf8_boxes": _read_option("PYTHON_TYRO_UTF8_BOXES", bool, True),
    "ansi_codes": _read_option("PYTHON_TYRO_ANSI_CODES", bool, True),
}


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
