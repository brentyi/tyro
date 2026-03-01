"""Test that UseAppendAction works correctly with various container types."""

import dataclasses
from typing import Tuple

import tyro


def test_append_with_list() -> None:
    """Verify UseAppendAction works with list."""

    @dataclasses.dataclass
    class WithList:
        items: tyro.conf.UseAppendAction[list[str]]

    result = tyro.cli(WithList, args="--items a --items b".split())
    assert result.items == ["a", "b"]


def test_append_with_set() -> None:
    """Verify UseAppendAction works with set."""

    @dataclasses.dataclass
    class WithSet:
        items: tyro.conf.UseAppendAction[set[str]]

    result = tyro.cli(WithSet, args="--items a --items b --items a".split())
    assert result.items == {"a", "b"}


def test_append_with_frozenset() -> None:
    """Verify UseAppendAction works with frozenset."""

    @dataclasses.dataclass
    class WithFrozenset:
        items: tyro.conf.UseAppendAction[frozenset[str]]

    result = tyro.cli(WithFrozenset, args="--items a --items b --items a".split())
    assert result.items == frozenset(["a", "b"])


def test_append_with_tuple() -> None:
    """Verify UseAppendAction works with tuple."""

    @dataclasses.dataclass
    class WithTuple:
        items: tyro.conf.UseAppendAction[Tuple[str, ...]]

    result = tyro.cli(WithTuple, args="--items a --items b".split())
    assert result.items == ("a", "b")
