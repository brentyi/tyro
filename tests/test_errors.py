import dataclasses
from typing import Generic, List, Tuple, TypeVar, Union

import pytest
from typing_extensions import Literal

import dcargs


def test_choices_in_tuples():
    """Due to argparse limitations, all parameters of `choices` must match. In the
    future, we might avoid this by implementing choice restrictions manually."""
    # OK
    @dataclasses.dataclass
    class A:  # type: ignore
        x: Tuple[bool, bool]

    assert dcargs.cli(A, args=["--x", "True", "False"]) == A((True, False))

    # OK
    @dataclasses.dataclass
    class A:  # type: ignore
        x: Tuple[bool, Literal["True", "False"]]

    assert dcargs.cli(A, args=["--x", "True", "False"]) == A((True, "False"))

    # Not OK: same argument, different choices.
    @dataclasses.dataclass
    class A:
        x: Tuple[bool, Literal["True", "False", "None"]]

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.cli(A, args=["--x", "True", "False"])


def test_nested_sequence_types():
    """Unclear how to handle nested sequences, so we don't support them."""

    @dataclasses.dataclass
    class A:
        x: Tuple[Tuple[int, ...], ...]

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.cli(A, args=["--x", "0", "1"])


def test_unsupported_literal():
    def main(x: Literal[0, "5"]) -> None:
        return

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.cli(main, args=[])


# Must be global.
@dataclasses.dataclass
class _CycleDataclass:
    x: "_CycleDataclass"


def test_cycle():
    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.cli(_CycleDataclass, args=[])


def test_uncallable_annotation():
    def main(arg: 5) -> None:  # type: ignore
        pass

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.cli(main, args=[])


def test_nested_annotation():
    @dataclasses.dataclass
    class OneIntArg:
        x: int

    def main(arg: List[OneIntArg]) -> List[OneIntArg]:  # type: ignore
        return arg

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.cli(main, args=[])

    @dataclasses.dataclass
    class OneStringArg:
        x: str

    def main(arg: List[OneStringArg]) -> List[OneStringArg]:  # type: ignore
        return arg

    assert dcargs.cli(main, args=["--arg", "0", "1", "2"]) == [
        OneStringArg("0"),
        OneStringArg("1"),
        OneStringArg("2"),
    ]

    @dataclasses.dataclass
    class TwoStringArg:
        x: str
        y: str

    def main(arg: List[TwoStringArg]) -> None:
        pass

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.cli(main, args=[])


def test_generic_inherited():
    """Inheriting from generics is currently not implemented. It's unclear whether this
    is feasible, because generics are lost in the mro:
    https://github.com/python/typing/issues/777"""

    class UnrelatedParentClass:
        pass

    T = TypeVar("T")

    @dataclasses.dataclass
    class ActualParentClass(Generic[T]):
        x: T  # Documentation 1

        # Documentation 2
        y: T

        z: T = 3  # type: ignore
        """Documentation 3"""

    @dataclasses.dataclass
    class ChildClass(UnrelatedParentClass, ActualParentClass[int]):
        pass

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.cli(ChildClass, args=["--x", "1", "--y", "2", "--z", "3"])


def test_unsupported_union():
    def main(a: Union[Tuple[int, int], Tuple[int, int, int]]) -> None:
        pass

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.cli(main, args=["--a", "5", "5"])


def test_missing_annotation():
    def main(a) -> None:
        pass

    with pytest.raises(TypeError):
        dcargs.cli(main, args=["--help"])
