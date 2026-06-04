"""Tests for chained PEP 696 TypeVar defaults.

When one TypeVar's default is another TypeVar (for example
``V = TypeVar("V", default=K)``), tyro should recursively resolve the default
through the active type parameter bindings rather than returning the raw inner
TypeVar (or falling back to the inner TypeVar's own default).
"""

import dataclasses
from typing import Generic, List, NamedTuple

import pydantic
import pytest
from typing_extensions import TypeVar

import tyro


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
