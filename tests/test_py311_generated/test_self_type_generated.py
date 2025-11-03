from __future__ import annotations

from typing import Self

import pytest

import tyro


class SomeClass:
    def __init__(self, a: int, b: int) -> None:
        self.a = a
        self.b = b

    def method1(self, x: Self) -> None:
        self.effect = x

    @classmethod
    def method2(cls, x: Self) -> SomeClass:
        return x

    # Self is not valid in static methods.
    # https://peps.python.org/pep-0673/#valid-locations-for-self
    #
    # @staticmethod
    # def method3(x: Self) -> TestClass:
    #     return x


class SomeSubclass(SomeClass): ...


def test_method() -> None:
    x = SomeClass(0, 0)
    with pytest.raises(SystemExit):
        tyro.cli(x.method1, args=[])

    assert tyro.cli(x.method1, args="--x.a 3 --x.b 3".split(" ")) is None
    assert x.effect.a == 3 and x.effect.b == 3
    assert isinstance(x, SomeClass)


def test_classmethod() -> None:
    x = SomeClass(0, 0)
    with pytest.raises(SystemExit):
        tyro.cli(x.method2, args=[])
    with pytest.raises(SystemExit):
        tyro.cli(SomeClass.method2, args=[])

    y = tyro.cli(x.method2, args="--x.a 3 --x.b 3".split(" "))
    assert y.a == 3
    assert y.b == 3
    assert isinstance(y, SomeClass)

    y = tyro.cli(SomeClass.method2, args="--x.a 3 --x.b 3".split(" "))
    assert y.a == 3
    assert y.b == 3
    assert isinstance(y, SomeClass)


def test_subclass_method() -> None:
    x = SomeSubclass(0, 0)
    with pytest.raises(SystemExit):
        tyro.cli(x.method1, args=[])

    assert tyro.cli(x.method1, args="--x.a 3 --x.b 3".split(" ")) is None
    assert x.effect.a == 3 and x.effect.b == 3
    assert isinstance(x, SomeSubclass)

    y = tyro.cli(x.method2, args="--x.a 3 --x.b 3".split(" "))
    assert y.a == 3
    assert y.b == 3
    assert isinstance(y, SomeClass)


def test_subclass_classmethod() -> None:
    x = SomeSubclass(0, 0)
    with pytest.raises(SystemExit):
        tyro.cli(x.method2, args=[])
    with pytest.raises(SystemExit):
        tyro.cli(SomeSubclass.method2, args=[])

    y = tyro.cli(x.method2, args="--x.a 3 --x.b 3".split(" "))
    assert y.a == 3
    assert y.b == 3
    assert isinstance(y, SomeClass)

    y = tyro.cli(SomeSubclass.method2, args="--x.a 3 --x.b 3".split(" "))
    assert y.a == 3
    assert y.b == 3
    assert isinstance(y, SomeClass)
