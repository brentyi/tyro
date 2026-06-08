"""Regression tests for bugs found via manual exploration.

Each test below fails on the unfixed code and documents the expected,
correct behavior.

* ``test_optional_fixed_length_tuple_accepts_none`` -- ``Optional`` of a
  fixed-length tuple (e.g. ``Optional[Tuple[int, int]]``) could not accept
  ``None`` on the CLI, because the union's computed ``nargs`` ignored the
  single-token ``NoneType`` option and demanded the tuple's exact count.

* ``test_clustered_value_short_with_equals`` -- POSIX-style short-flag
  clustering mishandled ``=`` inside a value-taking short's value. ``-na=foo``
  must parse to ``-n`` with value ``a=foo`` (matching argparse), and an ``=``
  immediately after the value-taking flag is a separator (``-abn=foo`` ->
  value ``foo``).

* ``test_subcommand_alias_delimiter_collision`` -- an alias whose delimiter-
  swapped form (``-``/``_``) matched a canonical name was wrongly rejected at
  construction, even though a registered alias is reachable by exact match
  (including the underscore form of a subcommand's own hyphenated canonical).
  Only an alias that *exactly* equals another canonical is a real collision.

* ``test_empty_tuple_nested_in_fixed_tuple`` -- an empty tuple ``Tuple[()]``
  nested inside another fixed tuple raised an internal ``AssertionError`` (or
  was wrongly rejected), because the backtracking parser could not handle a
  spec that consumes zero arguments.
"""

# pyright: reportOperatorIssue=false
# Suppression is for the auto-generated py311 copy of this file, where the
# Union-to-pipe rewrite produces `Annotated[...] | Annotated[...]` lines that
# pyright rejects even though they work at runtime.

from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import pytest
from typing_extensions import Annotated

import tyro
from tyro.conf import arg


def test_optional_fixed_length_tuple_accepts_none() -> None:
    # Direct form.
    assert tyro.cli(Optional[Tuple[int, int]], args=["None"]) is None
    assert tyro.cli(Optional[Tuple[int, int]], args=["1", "2"]) == (1, 2)

    # Dataclass field form.
    @dataclasses.dataclass
    class A:
        x: Optional[Tuple[int, int]] = None

    assert tyro.cli(A, args=[]) == A(x=None)
    assert tyro.cli(A, args=["--x", "None"]) == A(x=None)
    assert tyro.cli(A, args=["--x", "1", "2"]) == A(x=(1, 2))

    # Three-element fixed tuple too.
    assert tyro.cli(Optional[Tuple[int, int, int]], args=["None"]) is None
    assert tyro.cli(Optional[Tuple[int, int, int]], args=["1", "2", "3"]) == (1, 2, 3)


def test_clustered_value_short_with_equals() -> None:
    @dataclasses.dataclass
    class C:
        name: Annotated[str, arg(aliases=["-n"])] = "default"

    # `=` not immediately after the flag char -> part of the value.
    assert tyro.cli(C, args=["-na=foo"]).name == "a=foo"
    # `=` immediately after the (registered) short flag -> separator.
    assert tyro.cli(C, args=["-n=foo"]).name == "foo"
    # Glued, no `=`.
    assert tyro.cli(C, args=["-nfoo"]).name == "foo"
    # Multiple `=` after a cluster char.
    assert tyro.cli(C, args=["-nx=y"]).name == "x=y"

    @dataclasses.dataclass
    class D:
        a: Annotated[bool, arg(aliases=["-a"])] = False
        b: Annotated[bool, arg(aliases=["-b"])] = False
        n: Annotated[str, arg(aliases=["-n"])] = "default"

    # `=` immediately after the value-taking short at the end of a cluster is
    # a separator.
    assert tyro.cli(D, args=["-abn=foo"]) == D(a=True, b=True, n="foo")
    # `=` not immediately after the value-taking short -> part of the value.
    assert tyro.cli(D, args=["-an=b=c"]) == D(a=True, b=False, n="b=c")


def test_subcommand_alias_delimiter_collision() -> None:
    @dataclasses.dataclass
    class A:
        x: int = 1

    @dataclasses.dataclass
    class B:
        y: int = 2

    # Canonical `a-b` plus an `a_b` alias on a *different* subcommand: the alias
    # is reachable by exact match (typing `a_b` matches it before any delimiter
    # swap is attempted), so both spellings stay distinctly reachable. This must
    # be allowed rather than rejected -- the swapped form is not a collision.
    T = cast(
        Any,
        Union[
            Annotated[A, tyro.conf.subcommand("a-b")],
            Annotated[B, tyro.conf.subcommand("other", aliases=("a_b",))],
        ],
    )
    assert tyro.cli(T, args=["a-b"]) == A(x=1)
    assert tyro.cli(T, args=["a_b"]) == B(y=2)
    assert tyro.cli(T, args=["other"]) == B(y=2)

    # The reverse is NOT a collision: typing `a-b` does not resolve to a
    # canonical named `a_b`, so an `a-b` alias on a different subcommand is
    # legitimate and must be allowed.
    T2 = cast(
        Any,
        Union[
            Annotated[A, tyro.conf.subcommand("a_b")],
            Annotated[B, tyro.conf.subcommand("other", aliases=("a-b",))],
        ],
    )
    assert tyro.cli(T2, args=["a_b"]) == A(x=1)
    assert tyro.cli(T2, args=["a-b"]) == B(y=2)
    assert tyro.cli(T2, args=["other"]) == B(y=2)

    # Exact same spelling on two subcommands is still a collision.
    T3 = cast(
        Any,
        Union[
            Annotated[A, tyro.conf.subcommand("aa")],
            Annotated[B, tyro.conf.subcommand("other", aliases=("aa",))],
        ],
    )
    with pytest.raises(AssertionError):
        tyro.cli(T3, args=["aa"])


def test_empty_tuple_nested_in_fixed_tuple() -> None:
    # `Tuple[()]` nested inside another fixed tuple previously raised an
    # internal AssertionError ("At least one spec is required") or was wrongly
    # rejected, because the backtracking parser couldn't handle a spec that
    # consumes zero arguments.
    assert tyro.cli(Tuple[Tuple[()], int], args=["5"]) == ((), 5)
    assert tyro.cli(Tuple[int, Tuple[()]], args=["5"]) == (5, ())
    assert tyro.cli(Tuple[Tuple[()], int, Tuple[()]], args=["5"]) == ((), 5, ())

    # A genuinely-insufficient fixed tuple still errors (no over-eager
    # zero-width matching).
    with pytest.raises(SystemExit):
        tyro.cli(Tuple[int, str], args=["5"])


def test_repeating_zero_width_spec_terminates() -> None:
    # A repeated zero-width spec (e.g. `List[Tuple[()]]`) previously looped
    # forever in the backtracking parser when given non-empty input, because a
    # zero-width match advanced the spec index without consuming an argument.
    # It must instead reject the unconsumable input, and accept empty input.
    assert tyro.cli(List[Tuple[()]], args=[]) == []
    assert tyro.cli(Tuple[Tuple[()], ...], args=[]) == ()
    with pytest.raises(SystemExit):
        tyro.cli(List[Tuple[()]], args=["x"])
    with pytest.raises(SystemExit):
        tyro.cli(Tuple[Tuple[()], ...], args=["x"])

    # Normal repeating parses are unaffected.
    assert tyro.cli(List[int], args=["1", "2", "3"]) == [1, 2, 3]
    assert tyro.cli(List[Tuple[int, int]], args=["1", "2", "3", "4"]) == [
        (1, 2),
        (3, 4),
    ]


def test_repeated_multispec_trailing_zero_width_is_a_documented_limitation() -> None:
    # A repeating MULTI-spec container whose trailing spec is zero-width (e.g.
    # `Dict[str, Tuple[()]]`, repeating key + zero-width value) is rejected: see
    # the documented limitation in `_backtracking.py`. Allowing it would bypass
    # the zero-progress cycle pruning that is load-bearing for disambiguating
    # unions. This test pins that behavior so it isn't changed unintentionally.
    assert tyro.cli(Dict[str, Tuple[()]], args=[]) == {}  # empty is fine
    with pytest.raises(SystemExit):
        tyro.cli(Dict[str, Tuple[()]], args=["a"])

    # The load-bearing property the limitation protects: a mapping whose value
    # is a union that *includes* a zero-width option must still pick the wider
    # parse rather than the degenerate empty one.
    assert tyro.cli(
        Dict[str, Union[Tuple[()], Tuple[int, int]]], args=["k", "1", "2"]
    ) == {"k": (1, 2)}
