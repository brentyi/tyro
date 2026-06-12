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
from typing import TYPE_CHECKING, Any, Callable, List, Literal, Optional

from typing_extensions import TypedDict

from . import _fmtlib as fmt

if TYPE_CHECKING:
    from ._parsers import ArgWithContext, SubparsersSpecification


class ExperimentalOptionsDict(TypedDict):
    """Options for experimental tyro features.

    Attributes:
        enable_timing: Enable timing output for performance benchmarking.
        backend: Backend to use for parsing ("argparse" or "tyro").
        utf8_boxes: Enable UTF-8 box drawing characters in formatted output.
        ansi_codes: Enable ANSI color codes in formatted output.
        global_markers: Comma-separated names of :mod:`tyro.conf` markers to
            apply globally to every :func:`tyro.cli` call, in addition to any
            markers passed via ``config=``. Primarily useful for debugging, for
            example ``PYTHON_TYRO_GLOBAL_MARKERS=FlagConversionOff,ShowSourcePath``.
    """

    enable_timing: bool
    backend: Literal["argparse", "tyro"]
    utf8_boxes: bool
    ansi_codes: bool
    global_markers: str


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
    "global_markers": _read_option("PYTHON_TYRO_GLOBAL_MARKERS", str, ""),
}


def get_global_markers() -> tuple[Any, ...]:
    """Resolve the ``global_markers`` experimental option into marker objects.

    The option is a comma-separated string of marker names that exist in
    :mod:`tyro.conf` (e.g. ``"FlagConversionOff,ShowSourcePath"``). Each name is
    looked up via :func:`getattr` on the :mod:`tyro.conf` module. Returns an
    empty tuple when the option is unset.
    """
    markers_str = _experimental_options["global_markers"]
    if not markers_str:
        return ()

    # Imported lazily to avoid a circular import at module load time.
    from . import conf
    from .conf import _markers

    markers = []
    for name in markers_str.split(","):
        name = name.strip()
        if name == "":
            continue
        marker = getattr(conf, name, None)
        # Reject both unknown names and names that resolve to non-marker members
        # of `tyro.conf` (e.g. `arg`, `configure`), which would otherwise be
        # silently ignored.
        if not isinstance(marker, _markers._Marker):
            raise ValueError(
                f"Unknown marker {name!r} in the `global_markers` option "
                "(PYTHON_TYRO_GLOBAL_MARKERS). Expected the name of a marker in "
                "`tyro.conf`."
            )
        markers.append(marker)
    return tuple(markers)


missing_required_args_hook: Optional[Callable[[List["ArgWithContext"], dict], None]] = (
    None
)
"""Experimental hook fired by the default ("tyro") backend just before it reports
missing required arguments and exits.

Receives the list of missing arguments and the partial parse output (a dict keyed
by prefixed field names; subcommand selections are stored under
``f"{prefix} (positional)"`` keys). Intended for applications that embed tyro and
want to recover from missing arguments, e.g. by prompting the user interactively.
The hook may raise to take over error handling; if it returns normally, the
standard error message is printed and ``SystemExit(2)`` is raised.

May change or be removed in future versions."""

missing_subcommand_hook: Optional[Callable[["SubparsersSpecification", dict], None]] = (
    None
)
"""Experimental hook fired by the default ("tyro") backend just before it reports
a missing required subcommand and exits. Same contract as
:data:`missing_required_args_hook`; receives the unresolved
``SubparsersSpecification`` and the partial parse output.

May change or be removed in future versions."""


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
