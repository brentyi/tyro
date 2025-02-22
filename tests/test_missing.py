"""Tests for tyro.MISSING."""

import contextlib
import dataclasses
import io
from typing import Tuple, Union

import pytest

import tyro


def test_missing() -> None:
    def main(a: int = 5, b: int = tyro.MISSING, c: int = 3) -> Tuple[int, int, int]:
        return a, b, c

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stderr(target):
        tyro.cli(main, args=[])
    message = target.getvalue()
    assert "Required options" in message
    assert "Argument helptext" in message
    assert "--a INT" not in message
    assert "--b INT" in message
    assert "(required)" in message
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


def test_missing_in_dataclass_def() -> None:
    @dataclasses.dataclass
    class Child:
        a: int = 5
        b: int = 3
        c: int = 7

    @dataclasses.dataclass
    class Parent:
        child: Child = tyro.MISSING

    assert tyro.cli(
        Parent, args=["--child.a", "5", "--child.b", "7", "--child.c", "3"]
    ) == Parent(Child(5, 7, 3))

    with pytest.raises(SystemExit):
        tyro.cli(Parent, args=[], default=tyro.MISSING)

    # tyro.MISSING in dataclass definition should propagate to child fields, which makes all arguments required.
    with pytest.raises(SystemExit):
        tyro.cli(Parent, args=[])
    with pytest.raises(SystemExit):
        tyro.cli(Parent, args=["--child.a", "5"])


def test_missing_in_tuple() -> None:
    @dataclasses.dataclass
    class Child:
        a: int = 5
        b: int = 3
        c: int = 7

    @dataclasses.dataclass
    class Parent:
        child: Tuple[Child, Child] = tyro.MISSING

    with pytest.raises(SystemExit):
        tyro.cli(Parent, args=[])

    assert tyro.cli(
        Parent,
        args=[
            "--child.0.a",
            "5",
            "--child.0.b",
            "7",
            "--child.0.c",
            "3",
            "--child.1.a",
            "5",
            "--child.1.b",
            "7",
            "--child.1.c",
            "3",
        ],
    ) == Parent((Child(5, 7, 3), Child(5, 7, 3)))


def test_missing_in_tuple_pair() -> None:
    @dataclasses.dataclass
    class Child:
        a: int = 5
        b: int = 3
        c: int = 7

    @dataclasses.dataclass
    class Parent:
        child: Tuple[Child, Child] = (tyro.MISSING, tyro.MISSING)

    with pytest.raises(SystemExit):
        tyro.cli(Parent, args=[])

    assert tyro.cli(
        Parent,
        args=[
            "--child.0.a",
            "5",
            "--child.0.b",
            "7",
            "--child.0.c",
            "3",
            "--child.1.a",
            "5",
            "--child.1.b",
            "7",
            "--child.1.c",
            "3",
        ],
    ) == Parent((Child(5, 7, 3), Child(5, 7, 3)))


def test_missing_in_tuple_pair_subcommands() -> None:
    @dataclasses.dataclass
    class Child1:
        a: int = 5

    @dataclasses.dataclass
    class Child2:
        b: int = 3

    @dataclasses.dataclass
    class Parent:
        children: Tuple[Union[Child1, Child2], Union[Child1, Child2]] = (
            tyro.MISSING,
            Child2(2),
        )

    with pytest.raises(SystemExit):
        tyro.cli(Parent, args=[])

    assert tyro.cli(
        Parent,
        args=["children.0:child1", "--children.0.a", "5"],
    ) == Parent((Child1(5), Child2(2)))

    assert tyro.cli(
        Parent,
        args=["children.0:child2", "--children.0.b", "5"],
    ) == Parent((Child2(5), Child2(2)))
