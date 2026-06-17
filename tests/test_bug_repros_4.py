"""Regression tests for three fixes layered on top of the value-consumption and
subcommand-alias changes.

* ``test_negative_special_floats_are_values`` -- the fixed/variable-nargs
  flag-blocking heuristic treated ``-inf`` / ``-nan`` / ``-infinity`` as flags
  (because they start with a dash + alpha char), so a ``float`` field could not
  receive them even though ``float()`` accepts them. They must be consumed as
  values on the ``tyro`` backend, while genuinely flag-like tokens (``--verbose``)
  are still rejected.

* ``test_dash_prefixed_literal_choices_are_values`` -- a value that is an
  explicit ``choices`` entry (e.g. a dash-prefixed ``Literal`` like ``-b``) was
  rejected by the same heuristic before choice validation. A registered choice is
  unambiguous and must be consumed as a value on the ``tyro`` backend.

* ``test_subcommand_alias_with_swapped_delimiter_form`` -- an alias whose
  delimiter-swapped form (``_`` <-> ``-``) matched a canonical name was wrongly
  rejected at construction (e.g. ``run_server`` for a ``run-server`` subcommand --
  its own canonical). Such aliases are reachable by exact match and must be
  allowed; only an alias that *exactly* equals another canonical is rejected.
"""

# pyright: reportOperatorIssue=false
# Suppression is for the auto-generated py311 copy of this file, where the
# Union-to-pipe rewrite produces `Annotated[...] | Annotated[...]` lines that
# pyright rejects even though they work at runtime.

from __future__ import annotations

import dataclasses
import math
from typing import Any, List, Literal, Union

import pytest
from typing_extensions import Annotated

import tyro


def test_negative_special_floats_are_values(backend: str) -> None:
    @dataclasses.dataclass
    class A:
        x: float = 0.0

    # Ordinary negative numbers are values on both backends.
    assert tyro.cli(A, args=["--x", "-5"]).x == -5.0
    assert tyro.cli(A, args=["--x", "-2.5"]).x == -2.5

    if backend == "tyro":
        # Special float spellings are valid values too.
        assert math.isinf(tyro.cli(A, args=["--x", "-inf"]).x)
        assert tyro.cli(A, args=["--x", "-inf"]).x < 0
        assert math.isnan(tyro.cli(A, args=["--x", "-nan"]).x)
        assert math.isinf(tyro.cli(A, args=["--x", "-infinity"]).x)
        assert math.isinf(tyro.cli(A, args=["--x", "-Infinity"]).x)

        # They are also accepted mid-stream by a variable-length argument.
        @dataclasses.dataclass
        class B:
            xs: List[float] = dataclasses.field(default_factory=list)

        out = tyro.cli(B, args=["--xs", "1.0", "-inf"]).xs
        assert out[0] == 1.0 and math.isinf(out[1])
    else:
        # The argparse backend's negative-number matcher doesn't recognize
        # inf/nan; it still rejects them (unchanged, documented limitation).
        with pytest.raises(SystemExit):
            tyro.cli(A, args=["--x", "-inf"])

    # A genuinely flag-like value is still NOT swallowed (regression guard).
    @dataclasses.dataclass
    class C:
        x: float = 0.0
        verbose: bool = False

    with pytest.raises(SystemExit):
        tyro.cli(C, args=["--x", "--verbose"])


def test_dash_prefixed_literal_choices_are_values(backend: str) -> None:
    @dataclasses.dataclass
    class A:
        x: Literal["-a", "-b"] = "-a"

    if backend == "tyro":
        assert tyro.cli(A, args=["--x", "-b"]).x == "-b"
        assert tyro.cli(A, args=["--x", "-a"]).x == "-a"

        # In a variable-length argument too.
        @dataclasses.dataclass
        class B:
            xs: List[Literal["-a", "-b"]] = dataclasses.field(default_factory=list)

        assert tyro.cli(B, args=["--xs", "-a", "-b"]).xs == ["-a", "-b"]
    else:
        # The argparse backend cannot accept a dash-prefixed choice value.
        with pytest.raises(SystemExit):
            tyro.cli(A, args=["--x", "-b"])

    # A flag-like value that is NOT a registered choice is still rejected.
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "-c"])


def test_subcommand_alias_with_swapped_delimiter_form() -> None:
    # (a) A subcommand offering the underscore form of its OWN hyphenated
    # canonical name. `run_server` swaps to `run-server` (its own canonical) but
    # must still be allowed -- both spellings select RunServer.
    @dataclasses.dataclass
    class RunServer:
        port: int = 80

    @dataclasses.dataclass
    class Stop:
        v: int = 0

    M: Any = Union[
        Annotated[RunServer, tyro.conf.subcommand(aliases=["run_server"])],
        Stop,
    ]
    assert tyro.cli(M, args=["run-server", "--port", "9"]) == RunServer(port=9)
    assert tyro.cli(M, args=["run_server", "--port", "9"]) == RunServer(port=9)

    # (b) Two subcommands: canonical `a-b` and another whose alias `a_b` swaps to
    # `a-b`. Both remain distinctly reachable by their exact spellings.
    @dataclasses.dataclass
    class AB:
        v: int = 1

    @dataclasses.dataclass
    class Other:
        v: int = 2

    M2: Any = Union[
        Annotated[AB, tyro.conf.subcommand(name="a-b")],
        Annotated[Other, tyro.conf.subcommand(name="x", aliases=["a_b"])],
    ]
    assert tyro.cli(M2, args=["a-b"]) == AB(v=1)
    assert tyro.cli(M2, args=["a_b"]) == Other(v=2)


def test_subcommand_alias_exact_collision_still_rejected() -> None:
    # An alias that EXACTLY equals another subcommand's canonical name is a
    # genuine ambiguity and must still be rejected.
    @dataclasses.dataclass
    class P:
        v: int = 1

    @dataclasses.dataclass
    class Q:
        v: int = 2

    M: Any = Union[
        Annotated[P, tyro.conf.subcommand(name="foo")],
        Annotated[Q, tyro.conf.subcommand(name="bar", aliases=["foo"])],
    ]
    with pytest.raises(AssertionError):
        tyro.cli(M, args=["foo"])
