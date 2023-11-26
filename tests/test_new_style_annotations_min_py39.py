import dataclasses
from typing import Any, Literal, Optional, Union

import pytest

import tyro


def test_list() -> None:
    def main(x: list[bool]) -> Any:
        return x

    assert tyro.cli(main, args=["--x", "True", "False"]) == [True, False]


def test_tuple() -> None:
    def main(x: tuple[bool, str]) -> Any:
        return x

    assert tyro.cli(main, args=["--x", "True", "False"]) == (True, "False")


def test_tuple_nested() -> None:
    @dataclasses.dataclass
    class Args:
        a: int

    def main(x: tuple[Args, Args]) -> Any:
        return x

    assert tyro.cli(main, args=["--x.0.a", "3", "--x.1.a", "4"]) == (Args(3), Args(4))


def test_tuple_variable() -> None:
    def main(x: tuple[Union[bool, str], ...]) -> Any:
        return x

    assert tyro.cli(main, args=["--x", "True", "Wrong"]) == (True, "Wrong")


def test_super_nested() -> None:
    def main(
        x: Optional[
            list[
                tuple[
                    Optional[int],
                    Literal[3, 4],
                    Union[tuple[int, int], tuple[str, str]],
                ]
            ]
        ] = None
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


def test_tuple_direct() -> None:
    assert tyro.cli(tuple[int, ...], args="1 2".split(" ")) == (1, 2)  # type: ignore
    assert tyro.cli(tuple[int, int], args="1 2".split(" ")) == (1, 2)  # type: ignore
