import dataclasses
from typing import Any, Dict, Generic, List, Set, Tuple, TypeVar

import pytest

import dcargs


@dataclasses.dataclass(frozen=True)
class Color:
    r: int
    g: int
    b: int


def test_nested_tuple_fixed_single():
    def main(x: Tuple[Color]) -> Any:
        return x

    assert dcargs.cli(main, args="--x.0.r 255 --x.0.g 127 --x.0.b 5".split(" ")) == (
        Color(255, 127, 5),
    )


def test_nested_tuple_fixed_two():
    def main(x: Tuple[Color, Color]) -> Any:
        return x

    assert dcargs.cli(
        main,
        args=(
            "--x.0.r 255 --x.0.g 127 --x.0.b 5 --x.1.r 255 --x.1.g 127 --x.1.b 0"
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
            "--x.0.r 255 --x.0.g 127 --x.0.b 5 --x.1 94709 --x.2.r 255 --x.2.g 127"
            " --x.2.b 0"
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
            "--x.0.r 255 --x.0.g 127 --x.0.b 5 --x.1.0.r 255 --x.1.0.g 127 --x.1.0.b 0"
            " --x.1.1.r 255 --x.1.1.g 127 --x.1.1.b 0"
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


def test_set_bad():
    # Unable to infer input length.
    def main(x: Set[Color]) -> None:
        pass

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.cli(main, args=[])


def test_set_ok():
    def main(x: Set[Color] = {Color(255, 0, 0)}) -> Any:
        return x

    assert dcargs.cli(main, args=[]) == {Color(255, 0, 0)}
    assert dcargs.cli(main, args="--x.0.r 127".split(" ")) == {Color(127, 0, 0)}


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
    assert dcargs.cli(main, args="--x.0.r 127".split(" ")) == [Color(127, 0, 0)]


def test_list_object():
    def main(x: List[object] = [Color(255, 0, 0)]) -> Any:
        return x

    assert dcargs.cli(main, args=[]) == [Color(255, 0, 0)]
    assert dcargs.cli(main, args="--x.0.r 127".split(" ")) == [Color(127, 0, 0)]


def test_tuple_in_list():
    def main(x: List[Tuple[Color]] = [(Color(255, 0, 0),)]) -> Any:
        return x

    assert dcargs.cli(main, args=[]) == [(Color(255, 0, 0),)]
    assert dcargs.cli(main, args="--x.0.0.r 127".split(" ")) == [(Color(127, 0, 0),)]


def test_tuple_variable():
    def main(x: Tuple[Color, ...] = (Color(255, 0, 0), Color(255, 0, 127))) -> Any:
        return x

    assert dcargs.cli(main, args=[]) == (Color(255, 0, 0), Color(255, 0, 127))
    assert dcargs.cli(main, args="--x.0.r 127".split(" ")) == (
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


def test_dict_nested():
    def main(
        x: Dict[str, Tuple[Color, int]] = {
            # For each color: RGB and xterm color code.
            "red": (Color(255, 0, 0), 9),
            "green": (Color(0, 255, 0), 10),
            "blue": (Color(0, 0, 255), 12),
        }
    ) -> Any:
        return x

    assert dcargs.cli(main, args=[])["green"] == (Color(0, 255, 0), 10)
    assert dcargs.cli(main, args="--x.green.0.g 127 --x.green.1 2".split(" "))[
        "green"
    ] == (Color(0, 127, 0), 2)


def test_generic_in_tuple():
    ScalarType = TypeVar("ScalarType", int, float)

    @dataclasses.dataclass
    class GenericColor(Generic[ScalarType]):
        r: ScalarType
        g: ScalarType
        b: ScalarType

    def main(x: Tuple[GenericColor[float], GenericColor[int]]) -> Any:
        return x

    assert dcargs.cli(
        main,
        args=(
            "--x.0.r 0.5 --x.0.g 0.2 --x.0.b 0.3 --x.1.r 25 --x.1.g 2 --x.1.b 3".split(
                " "
            )
        ),
    ) == (GenericColor(0.5, 0.2, 0.3), GenericColor(25, 2, 3))


def test_generic_in_tuple_with_default():
    ScalarType = TypeVar("ScalarType", int, float)

    @dataclasses.dataclass
    class GenericColor(Generic[ScalarType]):
        r: ScalarType
        g: ScalarType
        b: ScalarType

    def main(
        x: Tuple[GenericColor[float], GenericColor[int]] = (
            GenericColor(0.5, 0.2, 0.3),
            GenericColor[int](25, 2, 3),  # The subscript should be optional.
        )
    ) -> Any:
        return x

    assert dcargs.cli(
        main,
        args=(
            "--x.0.r 0.5 --x.0.g 0.2 --x.0.b 0.3 --x.1.r 25 --x.1.g 2 --x.1.b 3".split(
                " "
            )
        ),
    ) == (GenericColor(0.5, 0.2, 0.3), GenericColor(25, 2, 3))


def test_generic_in_variable_tuple_with_default():
    ScalarType = TypeVar("ScalarType", int, float)

    @dataclasses.dataclass
    class GenericColor(Generic[ScalarType]):
        r: ScalarType
        g: ScalarType
        b: ScalarType

    def main(
        x: Tuple[GenericColor, ...] = (
            GenericColor[float](0.5, 0.2, 0.3),
            GenericColor[int](25, 2, 3),
        )
    ) -> Any:
        return x

    assert dcargs.cli(
        main,
        args=(
            "--x.0.r 0.5 --x.0.g 0.9 --x.0.b 0.3 --x.1.r 25 --x.1.g 2 --x.1.b 3".split(
                " "
            )
        ),
    ) == (GenericColor(0.5, 0.9, 0.3), GenericColor(25, 2, 3))


def test_generic_in_dict_with_default():
    ScalarType = TypeVar("ScalarType", int, float)

    @dataclasses.dataclass
    class GenericColor(Generic[ScalarType]):
        r: ScalarType
        g: ScalarType
        b: ScalarType

    def main(
        x: Dict[str, GenericColor] = {
            "float": GenericColor(0.5, 0.2, 0.3),
            "int": GenericColor[int](25, 2, 3),
        }
    ) -> Any:
        return x

    assert dcargs.cli(main, args="--x.float.g 0.1".split(" "),)[
        "float"
    ] == GenericColor(0.5, 0.1, 0.3)
    assert dcargs.cli(
        main,
        args="--x.int.g 0".split(" "),
    ) == {"float": GenericColor(0.5, 0.2, 0.3), "int": GenericColor(25, 0, 3)}
