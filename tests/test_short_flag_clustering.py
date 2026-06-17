"""Tests for POSIX-style short flag clustering (issue #465).

POSIX commands let you combine single-letter options: ``-abc`` is equivalent
to ``-a -b -c``. If a flag in the cluster takes a value, the rest of the
token (after an optional ``=``) becomes that value: ``-nfoo`` -> ``-n foo``.
"""

from __future__ import annotations

import dataclasses
from typing import Optional, Tuple

import pytest
from typing_extensions import Annotated

import tyro
from tyro.conf import UseCounterAction, arg


@dataclasses.dataclass
class Flags:
    a: Annotated[bool, arg(aliases=["-a"])] = False
    b: Annotated[bool, arg(aliases=["-b"])] = False
    c: Annotated[bool, arg(aliases=["-c"])] = False


def test_cluster_all_bool() -> None:
    out = tyro.cli(Flags, args=["-abc"])
    assert out == Flags(a=True, b=True, c=True)


def test_cluster_partial_bool() -> None:
    assert tyro.cli(Flags, args=["-ab"]) == Flags(a=True, b=True, c=False)
    assert tyro.cli(Flags, args=["-ac"]) == Flags(a=True, b=False, c=True)
    assert tyro.cli(Flags, args=["-bc"]) == Flags(a=False, b=True, c=True)


def test_cluster_with_separate_short() -> None:
    assert tyro.cli(Flags, args=["-ab", "-c"]) == Flags(a=True, b=True, c=True)
    assert tyro.cli(Flags, args=["-a", "-bc"]) == Flags(a=True, b=True, c=True)


def test_cluster_unknown_char_raises() -> None:
    with pytest.raises(SystemExit):
        tyro.cli(Flags, args=["-abz"])


def test_cluster_repeated_char_is_idempotent_for_bool() -> None:
    # -aa -> -a -a (both store_true, second overwrites; net effect a=True)
    assert tyro.cli(Flags, args=["-aa"]) == Flags(a=True)


def test_value_taking_short_glued() -> None:
    @dataclasses.dataclass
    class C:
        n: Annotated[str, arg(aliases=["-n"])] = "default"

    assert tyro.cli(C, args=["-nfoo"]).n == "foo"
    # -n=foo also works.
    assert tyro.cli(C, args=["-n=foo"]).n == "foo"
    # Spaced form still works.
    assert tyro.cli(C, args=["-n", "foo"]).n == "foo"


def test_value_taking_short_at_end_of_cluster() -> None:
    @dataclasses.dataclass
    class C:
        a: Annotated[bool, arg(aliases=["-a"])] = False
        b: Annotated[bool, arg(aliases=["-b"])] = False
        n: Annotated[str, arg(aliases=["-n"])] = "default"

    # -abn foo -> -a -b -n foo
    out = tyro.cli(C, args=["-abn", "foo"])
    assert out == C(a=True, b=True, n="foo")
    # Glued: -abnfoo -> -a -b -n foo
    out = tyro.cli(C, args=["-abnfoo"])
    assert out == C(a=True, b=True, n="foo")
    # Equals: -abn=foo
    out = tyro.cli(C, args=["-abn=foo"])
    assert out == C(a=True, b=True, n="foo")


def test_value_taking_short_in_middle_consumes_rest() -> None:
    """If a value-taking short appears mid-cluster, the rest is its value
    (POSIX semantics), even if subsequent characters look like other flags."""

    @dataclasses.dataclass
    class C:
        a: Annotated[bool, arg(aliases=["-a"])] = False
        b: Annotated[bool, arg(aliases=["-b"])] = False
        n: Annotated[str, arg(aliases=["-n"])] = "default"

    # -anb -> -a -n b (b becomes the value of -n, not a flag).
    out = tyro.cli(C, args=["-anb"])
    assert out == C(a=True, b=False, n="b")


def test_counter_short_cluster() -> None:
    @dataclasses.dataclass
    class C:
        verbose: Annotated[int, arg(aliases=["-v"]), UseCounterAction] = 0

    assert tyro.cli(C, args=["-vvv"]).verbose == 3
    assert tyro.cli(C, args=["-v", "-v"]).verbose == 2
    assert tyro.cli(C, args=[]).verbose == 0


def test_counter_mixed_with_bool_cluster() -> None:
    @dataclasses.dataclass
    class C:
        verbose: Annotated[int, arg(aliases=["-v"]), UseCounterAction] = 0
        a: Annotated[bool, arg(aliases=["-a"])] = False

    assert tyro.cli(C, args=["-va"]) == C(verbose=1, a=True)
    assert tyro.cli(C, args=["-vva"]) == C(verbose=2, a=True)
    assert tyro.cli(C, args=["-avv"]) == C(verbose=2, a=True)
    assert tyro.cli(C, args=["-vav"]) == C(verbose=2, a=True)


def test_registered_multichar_short_takes_precedence() -> None:
    """If ``-cail`` is explicitly registered as an alias, it must win over
    cluster expansion of ``-c -a -i -l``."""

    @dataclasses.dataclass
    class C:
        a: Annotated[bool, arg(aliases=["-a"])] = False
        c: Annotated[bool, arg(aliases=["-c"])] = False
        i: Annotated[bool, arg(aliases=["-i"])] = False
        l: Annotated[bool, arg(aliases=["-l"])] = False
        cail: Annotated[bool, arg(aliases=["-cail"])] = False

    out = tyro.cli(C, args=["-cail"])
    # The exact alias wins.
    assert out.cail is True
    assert out.a is False
    assert out.c is False


def test_double_dash_long_flag_not_clustered() -> None:
    """``--abc`` is a long flag; never expanded as a cluster."""

    @dataclasses.dataclass
    class C:
        a: Annotated[bool, arg(aliases=["-a"])] = False
        b: Annotated[bool, arg(aliases=["-b"])] = False
        c: Annotated[bool, arg(aliases=["-c"])] = False

    with pytest.raises(SystemExit):
        tyro.cli(C, args=["--abc"])


def test_cluster_after_double_dash_marker_treated_as_positional() -> None:
    """Tokens after the ``--`` end-of-options marker are not flags."""

    @dataclasses.dataclass
    class C:
        a: Annotated[bool, arg(aliases=["-a"])] = False
        rest: tyro.conf.Positional[Tuple[str, ...]] = ()

    out = tyro.cli(C, args=["-a", "--", "-bc"])
    assert out.a is True
    assert out.rest == ("-bc",)


def test_negative_number_not_cluster() -> None:
    """Negative numbers must still be parseable as positional/value args."""

    @dataclasses.dataclass
    class C:
        n: int = 0

    assert tyro.cli(C, args=["--n", "-3"]).n == -3


def test_cluster_with_value_taking_first() -> None:
    """If the first short in a cluster takes a value, the entire rest is
    its value (no further flag interpretation)."""

    @dataclasses.dataclass
    class C:
        n: Annotated[str, arg(aliases=["-n"])] = "x"
        a: Annotated[bool, arg(aliases=["-a"])] = False

    # -nabc -> -n abc, NOT -n -a -b -c.
    assert tyro.cli(C, args=["-nabc"]).n == "abc"


def test_cluster_int_value() -> None:
    @dataclasses.dataclass
    class C:
        a: Annotated[bool, arg(aliases=["-a"])] = False
        n: Annotated[int, arg(aliases=["-n"])] = 0

    out = tyro.cli(C, args=["-an42"])
    assert out == C(a=True, n=42)


def test_cluster_optional_value_taking() -> None:
    @dataclasses.dataclass
    class C:
        a: Annotated[bool, arg(aliases=["-a"])] = False
        n: Annotated[Optional[str], arg(aliases=["-n"])] = None

    out = tyro.cli(C, args=["-an", "hi"])
    assert out == C(a=True, n="hi")


def test_lone_short_not_affected() -> None:
    """Sanity check: lone ``-a`` still works."""

    out = tyro.cli(Flags, args=["-a"])
    assert out == Flags(a=True)


def test_cluster_does_not_match_long_flag_chars() -> None:
    """Cluster expansion must use only registered single-letter shorts, not
    arbitrary characters from long flag names."""

    @dataclasses.dataclass
    class C:
        apple: bool = False
        banana: bool = False

    with pytest.raises(SystemExit):
        tyro.cli(C, args=["-ab"])


def test_cluster_with_unrelated_short() -> None:
    """If only some chars are registered shorts, the cluster as a whole
    fails (we don't partial-expand)."""

    @dataclasses.dataclass
    class C:
        a: Annotated[bool, arg(aliases=["-a"])] = False
        # -b NOT registered.

    with pytest.raises(SystemExit):
        tyro.cli(C, args=["-ab"])


def test_help_short_unaffected() -> None:
    """``-h`` still triggers help and is not interpreted as a cluster."""

    @dataclasses.dataclass
    class C:
        a: Annotated[bool, arg(aliases=["-a"])] = False

    with pytest.raises(SystemExit) as exc_info:
        tyro.cli(C, args=["-h"])
    assert exc_info.value.code == 0


def test_glued_value_starting_with_dash() -> None:
    """A glued value attached to a value-taking short flag is consumed verbatim,
    even when it looks like a flag (e.g. ``-n-x`` -> ``-n`` with value ``-x``).
    This matches argparse; the value must NOT be rejected by the flag-like
    value-consumption guard."""

    @dataclasses.dataclass
    class C:
        name: Annotated[str, arg(aliases=["-n"])] = "default"

    assert tyro.cli(C, args=["-n-x"]).name == "-x"
    assert tyro.cli(C, args=["-n--x"]).name == "--x"
    assert tyro.cli(C, args=["-nab-c"]).name == "ab-c"
    assert tyro.cli(C, args=["-n=-x"]).name == "-x"
    # A separate (non-glued) flag-like token is still not a value.
    with pytest.raises(SystemExit):
        tyro.cli(C, args=["-n", "-x"])
