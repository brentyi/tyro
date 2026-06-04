# mypy: disable-error-code="call-overload,misc"
#
# Regression tests for abstract / subclass container annotations that were
# previously (incorrectly) treated as "fixed" arguments rather than being
# parsed. See: collections.abc.Set / MutableSet / MutableSequence /
# MutableMapping, and the dict subclasses collections.Counter / OrderedDict /
# defaultdict (plus their typing.* aliases).
import collections
import collections.abc
import dataclasses
from typing import Counter, DefaultDict, OrderedDict

import pytest

import tyro


# Set-like abstract base classes. ----------------------------------------


def test_abc_set() -> None:
    @dataclasses.dataclass
    class A:
        x: collections.abc.Set[int]

    out = tyro.cli(A, args=["--x", "1", "2", "3", "3"])
    assert out.x == frozenset({1, 2, 3})
    # `collections.abc.Set` is immutable -> frozenset.
    assert type(out.x) is frozenset
    assert tyro.cli(A, args=["--x"]).x == frozenset()
    assert type(tyro.cli(A, args=["--x"]).x) is frozenset
    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])


def test_abc_mutable_set() -> None:
    @dataclasses.dataclass
    class A:
        x: collections.abc.MutableSet[int]

    out = tyro.cli(A, args=["--x", "1", "2", "3", "3"])
    assert out.x == {1, 2, 3}
    assert type(out.x) is set
    assert tyro.cli(A, args=["--x"]).x == set()
    assert type(tyro.cli(A, args=["--x"]).x) is set


def test_abc_set_with_default() -> None:
    @dataclasses.dataclass
    class A:
        x: collections.abc.Set[int] = frozenset({0, 1, 2})

    # Round-trip: default is reused when no args are passed.
    assert tyro.cli(A, args=[]).x == frozenset({0, 1, 2})
    assert type(tyro.cli(A, args=[]).x) is frozenset
    assert tyro.cli(A, args=["--x", "5", "6"]).x == frozenset({5, 6})


# Sequence-like abstract base classes. ------------------------------------


def test_abc_mutable_sequence() -> None:
    @dataclasses.dataclass
    class A:
        x: collections.abc.MutableSequence[int]

    out = tyro.cli(A, args=["--x", "1", "2", "3"])
    assert out.x == [1, 2, 3]
    assert type(out.x) is list
    assert tyro.cli(A, args=["--x"]).x == []
    assert type(tyro.cli(A, args=["--x"]).x) is list


# Mapping-like abstract base classes and dict subclasses. -----------------


def test_abc_mutable_mapping() -> None:
    @dataclasses.dataclass
    class A:
        x: collections.abc.MutableMapping[str, int]

    out = tyro.cli(A, args=["--x", "a", "1", "b", "2"])
    assert out.x == {"a": 1, "b": 2}
    assert type(out.x) is dict
    assert tyro.cli(A, args=["--x"]).x == {}


def test_ordered_dict() -> None:
    @dataclasses.dataclass
    class A:
        x: collections.OrderedDict[str, int]

    out = tyro.cli(A, args=["--x", "a", "1", "b", "2"])
    assert out.x == collections.OrderedDict({"a": 1, "b": 2})
    assert isinstance(out.x, collections.OrderedDict)
    assert tyro.cli(A, args=["--x"]).x == collections.OrderedDict()
    assert isinstance(tyro.cli(A, args=["--x"]).x, collections.OrderedDict)


def test_typing_ordered_dict() -> None:
    @dataclasses.dataclass
    class A:
        x: OrderedDict[str, int]

    out = tyro.cli(A, args=["--x", "a", "1"])
    assert out.x == collections.OrderedDict({"a": 1})
    assert isinstance(out.x, collections.OrderedDict)


def test_counter() -> None:
    @dataclasses.dataclass
    class A:
        x: collections.Counter[str]

    out = tyro.cli(A, args=["--x", "a", "1", "b", "2"])
    assert out.x == collections.Counter({"a": 1, "b": 2})
    assert isinstance(out.x, collections.Counter)
    assert tyro.cli(A, args=["--x"]).x == collections.Counter()
    assert isinstance(tyro.cli(A, args=["--x"]).x, collections.Counter)


def test_typing_counter() -> None:
    @dataclasses.dataclass
    class A:
        x: Counter[str]

    out = tyro.cli(A, args=["--x", "a", "3"])
    assert out.x == collections.Counter({"a": 3})
    assert isinstance(out.x, collections.Counter)


def test_counter_with_default() -> None:
    @dataclasses.dataclass
    class A:
        x: collections.Counter[str] = dataclasses.field(
            default_factory=lambda: collections.Counter({"z": 3})
        )

    # Round-trip: default reused & re-validated when no args passed.
    out = tyro.cli(A, args=[])
    assert out.x == collections.Counter({"z": 3})
    assert isinstance(out.x, collections.Counter)


def test_defaultdict() -> None:
    @dataclasses.dataclass
    class A:
        x: collections.defaultdict[str, int]

    out = tyro.cli(A, args=["--x", "a", "1", "b", "2"])
    assert out.x == {"a": 1, "b": 2}
    assert isinstance(out.x, collections.defaultdict)
    # We construct `defaultdict(None, ...)`: there's no way to infer a
    # default_factory from the annotation, so missing keys raise KeyError.
    assert out.x.default_factory is None
    with pytest.raises(KeyError):
        out.x["missing"]


def test_typing_defaultdict() -> None:
    @dataclasses.dataclass
    class A:
        x: DefaultDict[str, int]

    out = tyro.cli(A, args=["--x", "a", "1"])
    assert out.x == {"a": 1}
    assert isinstance(out.x, collections.defaultdict)


# A mapping subclass we intentionally do NOT support: this should produce a
# clean "unsupported type annotation" error (SystemExit from the CLI parser),
# not a crash.
def test_chainmap_unsupported() -> None:
    @dataclasses.dataclass
    class A:
        x: collections.ChainMap[str, int]

    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "a", "1"])
