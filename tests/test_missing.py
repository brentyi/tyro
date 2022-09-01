"""Tests for dcargs.MISSING."""

import dataclasses
from typing import Tuple

import pytest

import dcargs


def test_missing():
    def main(a: int = 5, b: int = dcargs.MISSING, c: int = 3) -> Tuple[int, int, int]:
        return a, b, c

    with pytest.raises(SystemExit):
        dcargs.cli(main, args=[])
    assert dcargs.cli(main, args=["--b", "7"]) == (5, 7, 3)


def test_missing_dataclass():
    @dataclasses.dataclass
    class Args2:
        a: int = 5
        b: int = dcargs.MISSING
        c: int = 3

    with pytest.raises(SystemExit):
        dcargs.cli(Args2, args=[])
    assert dcargs.cli(Args2, args=["--b", "7"]) == Args2(5, 7, 3)


def test_missing_default():
    @dataclasses.dataclass
    class Args2:
        a: int
        b: int
        c: int

    with pytest.raises(SystemExit):
        dcargs.cli(
            Args2,
            args=[],
            default=Args2(5, dcargs.MISSING, 3),
        )
    assert dcargs.cli(
        Args2,
        args=["--b", "7"],
        default=Args2(5, dcargs.MISSING, 3),
    ) == Args2(5, 7, 3)


def test_missing_nested_default():
    @dataclasses.dataclass
    class Child:
        a: int = 5
        b: int = 3
        c: int = 7

    @dataclasses.dataclass
    class Parent:
        child: Child

    with pytest.raises(SystemExit):
        dcargs.cli(
            Parent,
            args=[],
            default=Parent(child=dcargs.MISSING),
        )
    assert dcargs.cli(
        Parent,
        args=["--child.a", "5", "--child.b", "7", "--child.c", "3"],
        default=Parent(child=dcargs.MISSING),
    ) == Parent(Child(5, 7, 3))
