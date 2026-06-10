"""Tests for chained PEP 696 TypeVar defaults.

When one TypeVar's default is another TypeVar (for example
``V = TypeVar("V", default=K)``), tyro should recursively resolve the default
through the active type parameter bindings rather than returning the raw inner
TypeVar (or falling back to the inner TypeVar's own default).
"""

import dataclasses
import sys
from typing import Any, Generic, List, NamedTuple, cast

import pydantic
import pytest
from typing_extensions import TypeVar

import tyro

# Explicitly parameterizing a generic that has a chained PEP 696 default with
# fewer args than parameters (e.g. `Entry[int]` where `V = TypeVar("V",
# default=K)`) requires the default slot to be filled into `__args__`
# (`(int, ~K)`). That only happens on Python 3.11+; on 3.8-3.10 `__args__` is
# just `(int,)` and the type cannot be resolved (this is a pre-existing Python
# limitation -- the base library crashes identically there). Tests that don't
# rely on this fill (bare defaults, single-level, overrides, sibling-binding)
# run on all versions.
needs_chained_default_fill = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="PEP 696 chained-default fill in Generic[...] subscription requires Python 3.11+",
)


@needs_chained_default_fill
def test_chained_default_explicit_binding() -> None:
    """Variant A: ``Entry[int]`` has ``__args__ == (int, ~K)``; ``V`` defaults to
    ``K``, which is bound to ``int``, so ``val`` should be parsed as ``int``."""
    K = TypeVar("K", default=str)
    V = TypeVar("V", default=K)

    @dataclasses.dataclass
    class Entry(Generic[K, V]):
        key: K
        val: V

    parsed = tyro.cli(Entry[int], args=["--key", "1", "--val", "2"])
    assert parsed == Entry(1, 2)
    assert isinstance(parsed.key, int)
    assert isinstance(parsed.val, int)


def test_chained_default_all_defaults() -> None:
    """Variant B: both TypeVars fall back to defaults. ``K`` defaults to ``int``
    and ``V`` defaults to ``K``, so both should resolve to ``int``."""
    K = TypeVar("K", default=int)
    V = TypeVar("V", default=K)

    @dataclasses.dataclass
    class Entry(Generic[K, V]):
        key: K
        val: V

    parsed = tyro.cli(Entry, args=["--key", "1", "--val", "2"])
    assert parsed == Entry(1, 2)
    assert isinstance(parsed.key, int)
    assert isinstance(parsed.val, int)


def test_single_level_default_still_works() -> None:
    """A plain (non-chained) PEP 696 default should still resolve."""
    K = TypeVar("K", default=int)

    @dataclasses.dataclass
    class Single(Generic[K]):
        x: K

    assert tyro.cli(Single, args=["--x", "5"]) == Single(5)
    assert tyro.cli(Single[str], args=["--x", "5"]) == Single("5")


@needs_chained_default_fill
def test_multi_level_chain() -> None:
    """W default=V default=K. A three-deep chain should fully resolve."""
    K = TypeVar("K", default=str)
    V = TypeVar("V", default=K)
    W = TypeVar("W", default=V)

    @dataclasses.dataclass
    class Triple(Generic[K, V, W]):
        a: K
        b: V
        c: W

    parsed = tyro.cli(Triple[int], args=["--a", "1", "--b", "2", "--c", "3"])
    assert parsed == Triple(1, 2, 3)
    assert all(isinstance(v, int) for v in (parsed.a, parsed.b, parsed.c))

    # All defaults: everything chains back to `str`.
    parsed = tyro.cli(Triple, args=["--a", "x", "--b", "y", "--c", "z"])
    assert parsed == Triple("x", "y", "z")


@needs_chained_default_fill
def test_chained_default_is_container() -> None:
    """A default that is a container of another TypeVar, e.g. ``default=List[K]``."""
    K = TypeVar("K", default=int)
    V = TypeVar("V", default=List[K])

    @dataclasses.dataclass
    class WithList(Generic[K, V]):
        key: K
        vals: V

    parsed = tyro.cli(WithList[float], args=["--key", "1.5", "--vals", "2.0", "3.0"])
    assert parsed == WithList(1.5, [2.0, 3.0])
    assert isinstance(parsed.key, float)
    assert parsed.vals == [2.0, 3.0]

    # All defaults: K -> int, V -> List[int].
    parsed = tyro.cli(WithList, args=["--key", "1", "--vals", "2", "3"])
    assert parsed == WithList(1, [2, 3])


def test_explicit_override_of_chained_param() -> None:
    """When the second parameter is given explicitly, the chain is not used."""
    K = TypeVar("K", default=str)
    V = TypeVar("V", default=K)

    @dataclasses.dataclass
    class Entry(Generic[K, V]):
        key: K
        val: V

    parsed = tyro.cli(Entry[int, bool], args=["--key", "1", "--val", "True"])
    assert parsed == Entry(1, True)
    assert isinstance(parsed.key, int)
    assert isinstance(parsed.val, bool)


def test_bound_typevar_not_broken() -> None:
    """Explicitly-parameterized bound TypeVars should still work."""
    B = TypeVar("B", bound=int)

    @dataclasses.dataclass
    class Bounded(Generic[B]):
        x: B

    assert tyro.cli(Bounded[int], args=["--x", "5"]) == Bounded(5)


def test_constrained_typevar_not_broken() -> None:
    """Explicitly-parameterized constrained TypeVars should still work."""
    C = TypeVar("C", int, str)

    @dataclasses.dataclass
    class Constrained(Generic[C]):
        x: C

    assert tyro.cli(Constrained[int], args=["--x", "5"]) == Constrained(5)


@needs_chained_default_fill
def test_chained_default_namedtuple() -> None:
    """Generic NamedTuple with a chained PEP 696 default."""
    K = TypeVar("K", default=str)
    V = TypeVar("V", default=K)

    class Pair(NamedTuple, Generic[K, V]):
        key: K
        val: V

    parsed = tyro.cli(Pair[int], args=["--key", "1", "--val", "2"])
    assert parsed == Pair(1, 2)
    assert isinstance(parsed.val, int)


@needs_chained_default_fill
def test_chained_default_pydantic() -> None:
    """Generic pydantic model with a chained PEP 696 default."""
    K = TypeVar("K", default=str)
    V = TypeVar("V", default=K)

    class Model(pydantic.BaseModel, Generic[K, V]):
        key: K
        val: V

    parsed = tyro.cli(Model[int], args=["--key", "1", "--val", "2"])
    assert parsed.key == 1
    assert parsed.val == 2
    assert isinstance(parsed.val, int)


def test_chained_default_no_infinite_loop() -> None:
    """A self-referential-ish default must not cause an infinite loop.

    ``V`` defaults to ``K`` and ``K`` defaults to ``V`` would be a true cycle,
    but Python forbids defining that. We instead exercise the guard via a chain
    where the terminal TypeVar has no resolution, which should terminate and
    fall back to ``Any`` (with a warning) rather than recursing forever.
    """
    K = TypeVar("K")  # No default, bound, or constraints.
    V = TypeVar("V", default=K)

    @dataclasses.dataclass
    class Entry(Generic[K, V]):
        key: K
        val: V

    # Should terminate: the chain bottoms out at an unresolvable TypeVar, which
    # resolves to `Any`. `Any` is not parsable, so we expect a clean SystemExit
    # rather than an infinite loop or hang.
    with pytest.warns(UserWarning):
        with pytest.raises(SystemExit):
            tyro.cli(Entry, args=["--key", "a", "--val", "b"])


def test_sibling_binding_does_not_shadow_enclosing_typevar() -> None:
    """Regression: the sibling-binding context pushed for a parameterized
    generic must not shadow a binding from an enclosing generic when a TypeVar
    *object* is reused across scopes.

    Here ``T`` is shared between ``OuterNest`` and ``Pair``. While resolving the
    field ``Pair[int, List[T]]``, the inner ``List[T]`` must keep the enclosing
    binding ``T -> str`` (from ``OuterNest[str]``), not be rebound to ``int`` by
    ``Pair``'s concrete first argument.
    """
    T = TypeVar("T")
    U = TypeVar("U")

    @dataclasses.dataclass
    class Pair(Generic[T, U]):
        first: T
        second: U

    @dataclasses.dataclass
    class OuterNest(Generic[T]):
        p: Pair[int, List[T]]
        bare: T

    out = tyro.cli(
        OuterNest[str],
        args=["--p.first", "1", "--p.second", "a", "b", "--bare", "z"],
    )
    assert out.p.first == 1
    assert out.p.second == ["a", "b"]  # List[str], not List[int]
    assert out.bare == "z"


def test_sibling_binding_three_level_nesting() -> None:
    """As above, but the shadowing binding is introduced by a middle generic."""
    T = TypeVar("T")
    U = TypeVar("U")

    @dataclasses.dataclass
    class Leaf(Generic[U]):
        v: U

    @dataclasses.dataclass
    class Mid(Generic[T, U]):
        leaf: Leaf[U]
        x: T

    @dataclasses.dataclass
    class Top(Generic[T]):
        m: Mid[int, List[T]]
        b: T

    out = tyro.cli(Top[str], args=["--m.leaf.v", "p", "q", "--m.x", "3", "--b", "w"])
    assert out.m.leaf.v == ["p", "q"]
    assert out.m.x == 3
    assert out.b == "w"


def test_free_typevar_subscription_falls_back_to_defaults() -> None:
    """Subscripting a generic with free defaulted TypeVars (its own, or
    permuted) must apply the PEP 696 defaults rather than failing to resolve.

    Regression test: the sibling-binding context used for chained defaults
    introduced identity bindings (``V -> V``) and two-cycles (``K -> V -> K``)
    that previously short-circuited resolution to a raw TypeVar, making these
    annotations error at parser construction."""
    K = TypeVar("K", default=int)
    V = TypeVar("V", default=str)

    @dataclasses.dataclass
    class Pair(Generic[K, V]):
        k: K
        v: V

    @dataclasses.dataclass
    class Box(Generic[K]):
        items: List[K]

    # `Any` aliases: type checkers reject free TypeVars in value-level
    # subscripts, but they are valid at runtime and the case under test.
    PairT: Any = Pair
    BoxT: Any = Box

    # Identity bindings: each free TypeVar falls back to its own default.
    assert tyro.cli(PairT[float, V], args=["--k", "3.5", "--v", "hello"]) == Pair(
        3.5, "hello"
    )
    assert tyro.cli(PairT[K, V], args=["--k", "3", "--v", "hello"]) == Pair(3, "hello")
    assert tyro.cli(BoxT[K], args=["--items", "1", "2"]) == Box(items=[1, 2])

    # Permuted two-cycle: Pair's K parameter is bound to the free V (default
    # str) and its V parameter to the free K (default int).
    assert tyro.cli(PairT[V, K], args=["--k", "hello", "--v", "3"]) == Pair("hello", 3)


def test_self_referential_typevar_default_terminates() -> None:
    """A TypeVar whose ``__default__`` is itself (only constructible by
    mutation) must terminate and resolve to the TypeVar unchanged."""
    from tyro._resolver import TypeParamResolver

    make_typevar = cast(Any, TypeVar)
    tv = make_typevar("SelfDefaultT")
    try:
        tv.__default__ = tv
    except (AttributeError, TypeError):  # pragma: no cover
        pytest.skip("TypeVar.__default__ is not assignable on this Python")
    assert TypeParamResolver.resolve_params_and_aliases(tv) is tv
