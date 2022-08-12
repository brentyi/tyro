import dataclasses
from typing import Any, Dict, List, Tuple

import pytest

import dcargs


@dataclasses.dataclass
class Color:
    r: int
    g: int
    b: int


def test_nested_tuple_fixed_single():
    def main(x: Tuple[Color]) -> Any:
        return x

    assert dcargs.cli(main, args="--x:0.r 255 --x:0.g 127 --x:0.b 5".split(" ")) == (
        Color(255, 127, 5),
    )


def test_nested_tuple_fixed_two():
    def main(x: Tuple[Color, Color]) -> Any:
        return x

    assert dcargs.cli(
        main,
        args=(
            "--x:0.r 255 --x:0.g 127 --x:0.b 5 --x:1.r 255 --x:1.g 127 --x:1.b 0"
        ).split(" "),
    ) == (
        Color(255, 127, 5),
        Color(255, 127, 0),
    )


def test_nested_tuple_fixed_three():
    def main(x: Tuple[Color, int, Color]) -> Any:
        return x

    assert dcargs.cli(
        main,
        args=(
            "--x:0.r 255 --x:0.g 127 --x:0.b 5 --x:1 94709 --x:2.r 255 --x:2.g 127"
            " --x:2.b 0"
        ).split(" "),
    ) == (
        Color(255, 127, 5),
        94709,
        Color(255, 127, 0),
    )


def test_nested_tuple_recursive():
    def main(x: Tuple[Color, Tuple[Color, Color]]) -> Any:
        return x

    assert dcargs.cli(
        main,
        args=(
            "--x:0.r 255 --x:0.g 127 --x:0.b 5 --x:1:0.r 255 --x:1:0.g 127 --x:1:0.b 0"
            " --x:1:1.r 255 --x:1:1.g 127 --x:1:1.b 0"
        ).split(" "),
    ) == (
        Color(255, 127, 5),
        (
            Color(255, 127, 0),
            Color(255, 127, 0),
        ),
    )


def test_tuple_bad():
    # Unable to infer input length.
    def main(x: Tuple[Color, ...]) -> None:
        pass

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.cli(main, args=[])


def test_list_bad():
    # Unable to infer input length.
    def main(x: List[Color]) -> None:
        pass

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.cli(main, args=[])


def test_list_ok():
    def main(x: List[Color] = [Color(255, 0, 0)]) -> Any:
        return x

    assert dcargs.cli(main, args=[]) == [Color(255, 0, 0)]
    assert dcargs.cli(main, args="--x:0.r 127".split(" ")) == [Color(127, 0, 0)]


def test_tuple_in_list():
    def main(x: List[Tuple[Color]] = [(Color(255, 0, 0),)]) -> Any:
        return x

    assert dcargs.cli(main, args=[]) == [(Color(255, 0, 0),)]
    assert dcargs.cli(main, args="--x:0:0.r 127".split(" ")) == [(Color(127, 0, 0),)]


def test_tuple_variable():
    def main(x: Tuple[Color, ...] = (Color(255, 0, 0), Color(255, 0, 127))) -> Any:
        return x

    assert dcargs.cli(main, args=[]) == (Color(255, 0, 0), Color(255, 0, 127))
    assert dcargs.cli(main, args="--x:0.r 127".split(" ")) == (
        Color(127, 0, 0),
        Color(255, 0, 127),
    )


def test_dict_bad():
    def main(x: Dict[str, Color]) -> Any:
        return x

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.cli(main, args=[])


def test_dict_ok():
    def main(
        x: Dict[str, Color] = {
            "red": Color(255, 0, 0),
            "green": Color(0, 255, 0),
            "blue": Color(0, 0, 255),
        }
    ) -> Any:
        return x

    assert dcargs.cli(main, args=[])["green"] == Color(0, 255, 0)
    assert dcargs.cli(main, args="--x.green.g 127".split(" "))["green"] == Color(
        0, 127, 0
    )
