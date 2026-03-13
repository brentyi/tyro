"""Tests for bugs in _calling.py argument handling and error reporting."""

import contextlib
import io

import pytest

import tyro
from tyro._strings import strip_ansi_sequences


def test_optional_group_missing_args_reports_all_missing() -> None:
    """When some args in an optional group are provided and others are missing,
    the error message should list ALL missing arguments, not just those before
    the first non-missing one.

    Bug: the loop in _calling.py used ``break`` instead of ``continue`` when
    encountering a non-missing kwarg, so missing args after it were silently
    dropped from the error message.
    """

    class Coord:
        """A coordinate with three required fields."""

        def __init__(self, a: int, b: int, c: int):
            self.a = a
            self.b = b
            self.c = c

    def main(coord: Coord = Coord(a=1, b=2, c=3)) -> Coord:
        return coord

    # Provide only --coord.b, leaving a and c unprovided.
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stderr(target):
        tyro.cli(main, args=["--coord.b", "20"])

    error = strip_ansi_sequences(target.getvalue())
    # Both --coord.a and --coord.c should be reported as missing.
    assert "--coord.a" in error, f"Expected --coord.a in error message, got: {error}"
    assert "--coord.c" in error, f"Expected --coord.c in error message, got: {error}"


def test_valueerror_no_message_in_constructor() -> None:
    """When a nested struct constructor raises ValueError() with no message,
    tyro should produce a clean error instead of crashing with IndexError.

    Bug: ``e.args[0]`` in _calling.py crashes with IndexError when
    ValueError() is raised with no arguments (empty args tuple).
    """

    class Validated:
        """A type whose constructor raises bare ValueError."""

        def __init__(self, x: int):
            if x > 10:
                raise ValueError()
            self.x = x

    def main(val: Validated = Validated(x=5)) -> Validated:
        return val

    # Should produce a SystemExit with a clean error, not an IndexError.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--val.x", "20"])
