# mypy: ignore-errors
#
# PEP 695 isn't yet supported in mypy. (April 4, 2024)
from dataclasses import dataclass

import tyro


def test_simple_generic():
    @dataclass(frozen=True)
    class Container[T]:
        a: T
        b: T

    assert tyro.cli(Container[int], args="--a 1 --b 2".split(" ")) == Container(1, 2)


type X = int
type Y = list[int]
type Z = Inner[int]


@dataclass(frozen=True)
class Inner[T]:
    a: T
    b: T


def test_generic_with_type_statement_0():
    @dataclass(frozen=True)
    class Container[T]:
        a: T
        b: T

    assert tyro.cli(Container[X], args="--a 1 --b 2".split(" ")) == Container(1, 2)


def test_generic_with_type_statement_1():
    @dataclass(frozen=True)
    class Container[T]:
        a: tuple[X, ...]
        b: T

    assert tyro.cli(Container[Y], args="--a 1 --b 2".split(" ")) == Container((1,), [2])


def test_generic_with_type_statement_2():
    @dataclass(frozen=True)
    class Container[T]:
        a: Z

    assert tyro.cli(Container[Y], args="--a.a 1 --a.b 2".split(" ")) == Container(
        Inner(1, 2)
    )
