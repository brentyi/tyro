# mypy: ignore-errors
#
# We can remove this ignore after: https://peps.python.org/pep-0747/

import dataclasses
from typing import Any, Literal, Type

import pytest

import tyro


def test_union_direct() -> None:
    assert tyro.cli(int | str, args=["5"]) == 5
    assert tyro.cli(int | str, args=["five"]) == "five"


def test_union_basic() -> None:
    def main(x: int | str) -> int | str:
        return x

    assert tyro.cli(main, args=["--x", "5"]) == 5
    assert tyro.cli(main, args=["--x", "6"]) == 6
    assert tyro.cli(main, args=["--x", "five"]) == "five"


def test_union_with_list() -> None:
    def main(x: int | str | list[bool]) -> Any:
        return x

    assert tyro.cli(main, args=["--x", "5"]) == 5
    assert tyro.cli(main, args=["--x", "6"]) == 6
    assert tyro.cli(main, args=["--x", "five"]) == "five"
    assert tyro.cli(main, args=["--x", "True"]) == "True"
    assert tyro.cli(main, args=["--x", "True", "False"]) == [True, False]


def test_union_literal() -> None:
    def main(x: Literal[1, 2] | Literal[3, 4, 5] | str) -> int | str:
        return x

    assert tyro.cli(main, args=["--x", "5"]) == 5
    assert tyro.cli(main, args=["--x", "6"]) == "6"
    assert tyro.cli(main, args=["--x", "five"]) == "five"


def test_super_nested() -> None:
    def main(
        x: (
            None
            | list[
                tuple[
                    None | int,
                    Literal[3, 4],
                    tuple[int, int] | tuple[str, str],
                ]
            ]
        ) = None,
    ) -> Any:
        return x

    assert tyro.cli(main, args=[]) is None
    assert tyro.cli(main, args="--x None".split(" ")) is None
    assert tyro.cli(main, args="--x None 3 2 2".split(" ")) == [(None, 3, (2, 2))]
    assert tyro.cli(main, args="--x 2 3 x 2".split(" ")) == [(2, 3, ("x", "2"))]
    assert tyro.cli(main, args="--x 2 3 x 2 2 3 1 2".split(" ")) == [
        (2, 3, ("x", "2")),
        (2, 3, (1, 2)),
    ]
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--help"])


def test_type() -> None:
    """Test adapted from mirceamironenco: https://github.com/brentyi/tyro/issues/164"""

    class Thing: ...

    class SubThing(Thing): ...

    @dataclasses.dataclass
    class Config:
        foo: int
        barr: type[Thing] = dataclasses.field(default=SubThing)
        bar: type[Thing] = dataclasses.field(default=SubThing)

    assert tyro.cli(Config, args=["--foo", "5"]) == Config(5, SubThing, SubThing)


def test_type_default_factory() -> None:
    """Test adapted from mirceamironenco: https://github.com/brentyi/tyro/issues/164"""

    @dataclasses.dataclass
    class Config:
        foo: int
        bar: type[Type] = dataclasses.field(default_factory=lambda: Type)

    assert tyro.cli(Config, args=["--foo", "5"]) == Config(5)
