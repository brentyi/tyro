"""Regression tests for the tyro-backend value-consumption fixes.

* ``test_fixed_nargs_does_not_swallow_flags`` -- a fixed-nargs argument (e.g. a
  single ``str`` or a ``Tuple[str, str]``) used to silently swallow a following
  flag-like token or the ``--`` end-of-options marker as its value (e.g.
  ``--x --verbose`` -> ``x='--verbose'``). It must instead error, matching
  argparse -- while still accepting a flag-like value attached with ``=``
  (``--x=--y``) and negative numbers (``--x -5``).

* ``test_variable_positional_reserves_for_later_positionals`` -- a variable
  length positional (e.g. ``Positional[List[int]]``) greedily consumed all
  remaining tokens, starving a later required positional. It must reserve the
  trailing values those positionals need, matching argparse.
"""

from __future__ import annotations

import dataclasses
from typing import List, Tuple

import pytest

import tyro
from tyro.conf import Positional


def test_fixed_nargs_does_not_swallow_flags() -> None:
    @dataclasses.dataclass
    class FS:
        x: str = "def"
        verbose: bool = False

    # A space-separated flag must not be consumed as the value.
    with pytest.raises(SystemExit):
        tyro.cli(FS, args=["--x", "--verbose"])
    with pytest.raises(SystemExit):
        tyro.cli(FS, args=["--x", "--y"])  # unknown but flag-like

    # The `--` end-of-options marker must not be consumed as a value.
    @dataclasses.dataclass
    class T2:
        pair: Tuple[str, str] = ("a", "b")

    with pytest.raises(SystemExit):
        tyro.cli(T2, args=["--pair", "--", "x"])

    # A flag-like value attached with `=` is still accepted verbatim.
    assert tyro.cli(FS, args=["--x=--y"]).x == "--y"
    # Negative numbers are still values.
    assert tyro.cli(FS, args=["--x", "-5"]).x == "-5"
    # Normal usage unaffected; a flag after a satisfied value still parses.
    assert tyro.cli(FS, args=["--x", "hi", "--verbose"]) == FS(x="hi", verbose=True)
    assert tyro.cli(T2, args=["--pair", "x", "y"]).pair == ("x", "y")


def test_variable_positional_reserves_for_later_positionals() -> None:
    @dataclasses.dataclass
    class A:
        xs: Positional[List[int]]
        y: Positional[int]

    assert tyro.cli(A, args=["1", "2", "3", "4"]) == A(xs=[1, 2, 3], y=4)
    assert tyro.cli(A, args=["1"]) == A(xs=[], y=1)

    # Two trailing required positionals.
    @dataclasses.dataclass
    class B:
        xs: Positional[List[int]]
        y: Positional[int]
        z: Positional[int]

    assert tyro.cli(B, args=["1", "2", "3", "4", "5"]) == B(xs=[1, 2, 3], y=4, z=5)

    # A leading fixed positional followed by a greedy one is unaffected.
    @dataclasses.dataclass
    class C:
        a: Positional[int]
        xs: Positional[List[str]]

    assert tyro.cli(C, args=["1", "a", "b", "c"]) == C(a=1, xs=["a", "b", "c"])

    # A lone greedy positional still consumes everything.
    @dataclasses.dataclass
    class D:
        xs: Positional[List[int]]

    assert tyro.cli(D, args=["1", "2", "3"]) == D(xs=[1, 2, 3])
