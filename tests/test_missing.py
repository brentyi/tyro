"""Tests for tyro.MISSING."""

import dataclasses
from typing import Tuple

import pytest

import tyro


def test_missing() -> None:
    def main(a: int = 5, b: int = tyro.MISSING, c: int = 3) -> Tuple[int, int, int]:
        return a, b, c

    with pytest.raises(SystemExit):
        tyro.cli(main, args=[])
    assert tyro.cli(main, args=["--b", "7"]) == (5, 7, 3)


def test_missing_dataclass() -> None:
    @dataclasses.dataclass
    class Args2:
        a: int = 5
        b: int = tyro.MISSING
        c: int = 3

    with pytest.raises(SystemExit):
        tyro.cli(Args2, args=[])
    assert tyro.cli(Args2, args=["--b", "7"]) == Args2(5, 7, 3)


def test_missing_default() -> None:
    @dataclasses.dataclass
    class Args2:
        a: int
        b: int
        c: int

    with pytest.raises(SystemExit):
        tyro.cli(
            Args2,
            args=[],
            default=Args2(5, tyro.MISSING, 3),
        )
    assert tyro.cli(
        Args2,
        args=["--b", "7"],
        default=Args2(5, tyro.MISSING, 3),
    ) == Args2(5, 7, 3)


def test_missing_nested_default() -> None:
    @dataclasses.dataclass
    class Child:
        a: int = 5
        b: int = 3
        c: int = 7

    @dataclasses.dataclass
    class Parent:
        child: Child

    with pytest.raises(SystemExit):
        tyro.cli(
            Parent,
            args=[],
            default=Parent(child=tyro.MISSING),
        )
    assert tyro.cli(
        Parent,
        args=["--child.a", "5", "--child.b", "7", "--child.c", "3"],
        default=Parent(child=tyro.MISSING),
    ) == Parent(Child(5, 7, 3))
