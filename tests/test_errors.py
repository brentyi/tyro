import dataclasses
from typing import List, Tuple, TypeVar, Union

import pytest

import tyro


def test_ambiguous_collection_0() -> None:
    @dataclasses.dataclass
    class A:
        x: Tuple[Tuple[int, ...], ...]

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(A, args=["--x", "0", "1"])


def test_ambiguous_collection_1() -> None:
    @dataclasses.dataclass
    class A:
        x: List[List[int]]

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(A, args=["--x", "0", "1"])


def test_ambiguous_collection_2() -> None:
    def main(x: Tuple[List[str], List[str]]) -> None:
        pass

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--help"])


def test_ambiguous_collection_3() -> None:
    def main(x: List[Union[Tuple[int, int], Tuple[int, int, int]]]) -> None:
        pass

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--help"])


# Must be global.
@dataclasses.dataclass
class _CycleDataclass:
    x: "_CycleDataclass"


def test_cycle() -> None:
    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(_CycleDataclass, args=[])


def test_uncallable_annotation() -> None:
    def main(arg: 5) -> None:  # type: ignore
        pass

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=[])


def test_nested_annotation() -> None:
    @dataclasses.dataclass
    class OneIntArg:
        x: int

    def main(arg: List[OneIntArg]) -> List[OneIntArg]:  # type: ignore
        return arg

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=[])

    @dataclasses.dataclass
    class OneStringArg:
        x: str

    def main(arg: List[OneStringArg]) -> List[OneStringArg]:  # type: ignore
        return arg

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--arg", "0", "1", "2"])

    @dataclasses.dataclass
    class TwoStringArg:
        x: str
        y: str

    def main2(arg: List[TwoStringArg]) -> None:
        pass

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main2, args=[])


def test_missing_annotation_1() -> None:
    def main(a, b) -> None:
        pass

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--help"])


def test_missing_annotation_2() -> None:
    def main(*, a) -> None:
        pass

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--help"])


def test_tuple_needs_default() -> None:
    def main(arg: tuple) -> None:  # type: ignore
        pass

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--help"])


def test_unbound_typevar() -> None:
    T = TypeVar("T")

    def main(arg: T) -> None:  # type: ignore
        pass

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--help"])


def test_missing_default_fixed() -> None:
    def main(value: tyro.conf.SuppressFixed[tyro.conf.Fixed[int]]) -> int:
        return value

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--help"])


def test_missing_default_suppressed() -> None:
    def main(value: tyro.conf.Suppress[int]) -> int:
        return value

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--help"])


def test_ambiguous_sequence() -> None:
    def main(value: list) -> None:
        return None

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--help"])
