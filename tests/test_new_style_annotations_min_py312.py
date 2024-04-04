from dataclasses import dataclass

import tyro


def test_simple_generic():
    @dataclass(frozen=True)
    class Container[T]:
        a: T
        b: T

    assert tyro.cli(Container[int], args="--a 1 --b 2".split(" ")) == Container(1, 2)
