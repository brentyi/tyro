from __future__ import annotations

import pytest
from typing_extensions import Self

import tyro


class TestClass:
    def __init__(self, a: int, b: int) -> None:
        self.a = a
        self.b = b

    def method1(self, x: Self) -> None:
        self.effect = x

    @classmethod
    def method2(cls, x: Self) -> TestClass:
        return x

    # Self is not valid in static methods.
    # https://peps.python.org/pep-0673/#valid-locations-for-self
    #
    # @staticmethod
    # def method3(x: Self) -> TestClass:
    #     return x


class TestSubclass(TestClass):
    ...


def test_method() -> None:
    x = TestClass(0, 0)
    with pytest.raises(SystemExit):
        tyro.cli(x.method1, args=[])

    assert tyro.cli(x.method1, args="--x.a 3 --x.b 3".split(" ")) is None
    assert x.effect.a == 3 and x.effect.b == 3
    assert isinstance(x, TestClass)


def test_classmethod() -> None:
    x = TestClass(0, 0)
    with pytest.raises(SystemExit):
        tyro.cli(x.method2, args=[])
    with pytest.raises(SystemExit):
        tyro.cli(TestClass.method2, args=[])

    y = tyro.cli(x.method2, args="--x.a 3 --x.b 3".split(" "))
    assert y.a == 3
    assert y.b == 3
    assert isinstance(y, TestClass)

    y = tyro.cli(TestClass.method2, args="--x.a 3 --x.b 3".split(" "))
    assert y.a == 3
    assert y.b == 3
    assert isinstance(y, TestClass)


def test_subclass_method() -> None:
    x = TestSubclass(0, 0)
    with pytest.raises(SystemExit):
        tyro.cli(x.method1, args=[])

    assert tyro.cli(x.method1, args="--x.a 3 --x.b 3".split(" ")) is None
    assert x.effect.a == 3 and x.effect.b == 3
    assert isinstance(x, TestSubclass)

    y = tyro.cli(x.method2, args="--x.a 3 --x.b 3".split(" "))
    assert y.a == 3
    assert y.b == 3
    assert isinstance(y, TestClass)


def test_subclass_classmethod() -> None:
    x = TestSubclass(0, 0)
    with pytest.raises(SystemExit):
        tyro.cli(x.method2, args=[])
    with pytest.raises(SystemExit):
        tyro.cli(TestSubclass.method2, args=[])

    y = tyro.cli(x.method2, args="--x.a 3 --x.b 3".split(" "))
    assert y.a == 3
    assert y.b == 3
    assert isinstance(y, TestClass)

    y = tyro.cli(TestSubclass.method2, args="--x.a 3 --x.b 3".split(" "))
    assert y.a == 3
    assert y.b == 3
    assert isinstance(y, TestClass)
