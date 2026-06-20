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

* ``test_dash_prefixed_literal_values_in_fixed_arity_containers`` -- the same
  heuristic rejected dash-prefixed ``Literal`` values inside a fixed-arity
  container (e.g. a heterogeneous ``Tuple``), where the argument-level
  ``choices`` is ``None``. The per-element choices are now aggregated so these
  tokens are consumed as values on the ``tyro`` backend.

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
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple

import pytest

import tyro
from tyro.constructors import PrimitiveConstructorSpec


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


def test_dash_prefixed_literal_values_in_fixed_arity_containers(backend: str) -> None:
    # Regression: dash-prefixed `Literal` values inside a fixed-arity container
    # (e.g. a heterogeneous `Tuple`) were rejected on the `tyro` backend. Such a
    # container's argument-level `choices` is None (per-element choices are not
    # lifted), so the flag-blocking heuristic in `_consume_argument` treated
    # `-a`/`-b` as flags and raised a spurious "Expected N values" error. The
    # values must instead be recognized via the per-position choice values,
    # collected from the type at lowering time.
    @dataclasses.dataclass
    class Pair:
        xy: Tuple[Literal["-a", "-b"], Literal["-a", "-b"]]

    @dataclasses.dataclass
    class Mixed:
        # First element is an int (not a choice); second is a dash-Literal.
        xy: Tuple[int, Literal["-a", "-b"]]

    @dataclasses.dataclass
    class Mapping:
        m: Dict[Literal["-a"], Literal["-b"]]

    @dataclasses.dataclass
    class OptionalPair:
        xy: Optional[Tuple[Literal["-a"], Literal["-b"]]] = None

    if backend == "tyro":
        assert tyro.cli(Pair, args=["--xy", "-a", "-b"]).xy == ("-a", "-b")
        assert tyro.cli(Mixed, args=["--xy", "5", "-a"]).xy == (5, "-a")
        assert tyro.cli(Mapping, args=["--m", "-a", "-b"]).m == {"-a": "-b"}
        # Union: both the tuple form and the `None` token still parse.
        assert tyro.cli(OptionalPair, args=["--xy", "-a", "-b"]).xy == ("-a", "-b")
        assert tyro.cli(OptionalPair, args=["--xy", "None"]).xy is None

        # A flag-like token that is NOT a registered value still terminates
        # consumption and errors (regression guard).
        with pytest.raises(SystemExit):
            tyro.cli(Pair, args=["--xy", "-a", "-c"])
    else:
        # The argparse backend cannot accept dash-prefixed choice values; it
        # rejects them (unchanged, documented limitation).
        with pytest.raises(SystemExit):
            tyro.cli(Pair, args=["--xy", "-a", "-b"])


# A custom primitive spec whose values are dash-prefixed. Defined at module
# scope so its `Annotated[...]` use resolves under `from __future__ import
# annotations`.
_DASH_SPEC: Any = PrimitiveConstructorSpec(
    nargs=1,
    metavar="{-x,-y}",
    instance_from_str=lambda a: a[0],
    is_instance=lambda x: x in ("-x", "-y"),
    str_from_instance=lambda x: [x],
    choices=("-x", "-y"),
)


@dataclasses.dataclass
class _CustomDashList:
    xs: List[Annotated[str, _DASH_SPEC]] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class _CustomDashPair:
    xy: Tuple[Annotated[str, _DASH_SPEC], Annotated[str, _DASH_SPEC]] = ("-x", "-y")


def test_custom_spec_dash_values_are_recognized(backend: str) -> None:
    # The flag-vs-value carve-out keys off each leaf's `choices`, not just
    # `Literal` -- so a custom `PrimitiveConstructorSpec` with dash-prefixed
    # choices is recognized too, in both homogeneous and heterogeneous
    # containers. (The homogeneous-list case worked before this was derived from
    # the type at lowering; the heterogeneous tuple is newly supported.)
    if backend == "tyro":
        assert tyro.cli(_CustomDashList, args=["--xs", "-x", "-y"]).xs == ["-x", "-y"]
        assert tyro.cli(_CustomDashPair, args=["--xy", "-x", "-y"]).xy == ("-x", "-y")
    else:
        with pytest.raises(SystemExit):
            tyro.cli(_CustomDashPair, args=["--xy", "-x", "-y"])


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

    M: Any = Annotated[RunServer, tyro.conf.subcommand(aliases=["run_server"])] | Stop
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

    M2: Any = (
        Annotated[AB, tyro.conf.subcommand(name="a-b")]
        | Annotated[Other, tyro.conf.subcommand(name="x", aliases=["a_b"])]
    )
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

    M: Any = (
        Annotated[P, tyro.conf.subcommand(name="foo")]
        | Annotated[Q, tyro.conf.subcommand(name="bar", aliases=["foo"])]
    )
    with pytest.raises(AssertionError):
        tyro.cli(M, args=["foo"])
