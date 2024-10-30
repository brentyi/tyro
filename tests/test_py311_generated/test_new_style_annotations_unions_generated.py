from __future__ import annotations  # Should enable support for all versions of Python.

from typing import Any, Literal

import pytest

import tyro


def test_union_basic():
    def main(x: int | str) -> int | str:
        return x

    assert tyro.cli(main, args=["--x", "5"]) == 5
    assert tyro.cli(main, args=["--x", "6"]) == 6
    assert tyro.cli(main, args=["--x", "five"]) == "five"


def test_union_with_list():
    def main(x: int | str | list[bool]) -> Any:
        return x

    assert tyro.cli(main, args=["--x", "5"]) == 5
    assert tyro.cli(main, args=["--x", "6"]) == 6
    assert tyro.cli(main, args=["--x", "five"]) == "five"
    assert tyro.cli(main, args=["--x", "True"]) == "True"
    assert tyro.cli(main, args=["--x", "True", "False"]) == [True, False]


def test_union_literal():
    def main(x: Literal[1, 2] | Literal[3, 4, 5] | str) -> int | str:
        return x

    assert tyro.cli(main, args=["--x", "5"]) == 5
    assert tyro.cli(main, args=["--x", "6"]) == "6"
    assert tyro.cli(main, args=["--x", "five"]) == "five"


def test_super_nested():
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
