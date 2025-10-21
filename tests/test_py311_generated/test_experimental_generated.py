"""Tests for experimental features."""

import dataclasses
import sys
from io import StringIO

import tyro


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
