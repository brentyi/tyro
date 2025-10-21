"""Experimental features and settings for tyro.

This module contains experimental features and settings that may change or be removed
in future versions. Use with caution in production code.
"""

from __future__ import annotations

import os
from typing import Any, Literal

from typing_extensions import TypedDict

from . import _fmtlib as fmt


class ExperimentalOptionsDict(TypedDict):
    """Options for experimental tyro features.

    Attributes:
        enable_timing: Enable timing output for performance benchmarking.
        backend: Backend to use for parsing ("argparse" or "tyro").
    """

    enable_timing: bool
    backend: Literal["argparse", "tyro"]


def read_option(str_name: str, typ: Any, default: Any) -> Any:  # pragma: no cover
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
    "enable_timing": read_option("PYTHON_TYRO_ENABLE_TIMING", bool, False),
    "backend": read_option("PYTHON_TYRO_BACKEND", Literal["argparse", "tyro"], "tyro"),
}

# Backward compatibility alias.
options = _experimental_options


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
