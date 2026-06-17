"""Tests for experimental features."""

import dataclasses
import sys
from io import StringIO

import pytest

import tyro
from tyro import _settings


def test_enable_timing() -> None:
    """Test that timing can be enabled and produces output."""

    @dataclasses.dataclass
    class Args:
        x: int = 5

    # Enable timing.
    tyro._experimental_options["enable_timing"] = True

    # Capture stderr to check for timing output.
    old_stderr = sys.stderr
    sys.stderr = StringIO()

    try:
        result = tyro.cli(Args, args=["--x", "10"])
        assert result.x == 10

        # Check that timing output was produced.
        stderr_output = sys.stderr.getvalue()
        assert "took" in stderr_output
        assert "seconds" in stderr_output
    finally:
        # Restore stderr and disable timing.
        sys.stderr = old_stderr
        tyro._experimental_options["enable_timing"] = False


def test_global_markers_helper() -> None:
    """`global_markers` is parsed into marker objects from `tyro.conf`."""
    try:
        # Unset -> no markers.
        tyro._experimental_options["global_markers"] = ""
        assert _settings.get_global_markers() == ()

        # Comma-separated names resolve to markers; whitespace is tolerated.
        tyro._experimental_options["global_markers"] = (
            "FlagConversionOff, ShowSourcePath"
        )
        assert _settings.get_global_markers() == (
            tyro.conf.FlagConversionOff,
            tyro.conf.ShowSourcePath,
        )

        # Unknown names raise.
        tyro._experimental_options["global_markers"] = "NotARealMarker"
        with pytest.raises(ValueError):
            _settings.get_global_markers()

        # Names that exist in `tyro.conf` but aren't markers (e.g. `arg`) also
        # raise, rather than being silently ignored.
        tyro._experimental_options["global_markers"] = "arg"
        with pytest.raises(ValueError):
            _settings.get_global_markers()
    finally:
        tyro._experimental_options["global_markers"] = ""


def test_global_markers_applied() -> None:
    """Markers from `global_markers` are applied to every `tyro.cli` call."""

    @dataclasses.dataclass
    class Args:
        flag: bool = False

    try:
        tyro._experimental_options["global_markers"] = "FlagConversionOff"
        # With FlagConversionOff, the flag takes an explicit value and the
        # `--no-flag` form is not generated.
        assert tyro.cli(Args, args=["--flag", "True"]).flag is True
        with pytest.raises(SystemExit):
            tyro.cli(Args, args=["--no-flag"], console_outputs=False)
    finally:
        tyro._experimental_options["global_markers"] = ""
