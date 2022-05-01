import dataclasses
import enum
from typing import Generic, List, Tuple, Type, TypeVar, Union

import pytest

import dcargs

T = TypeVar("T")


def _check_serialization_identity(cls: Type[T], instance: T) -> None:
    assert dcargs.from_yaml(cls, dcargs.to_yaml(instance)) == instance


ScalarType = TypeVar("ScalarType")


def test_tuple_generic_variable():
    @dataclasses.dataclass
    class TupleGenericVariable(Generic[ScalarType]):
        xyz: Tuple[ScalarType, ...]

    assert dcargs.parse(
        TupleGenericVariable[int], args=["--xyz", "1", "2", "3"]
    ) == TupleGenericVariable((1, 2, 3))


def test_tuple_generic_fixed():
    @dataclasses.dataclass
    class TupleGenericFixed(Generic[ScalarType]):
        xyz: Tuple[ScalarType, ScalarType, ScalarType]

    assert dcargs.parse(
        TupleGenericFixed[int], args=["--xyz", "1", "2", "3"]
    ) == TupleGenericFixed((1, 2, 3))


class CoordinateFrame(enum.Enum):
    WORLD = enum.auto()
    CAMERA = enum.auto()


@dataclasses.dataclass
class Point3(Generic[ScalarType]):
    x: ScalarType
    y: ScalarType
    z: ScalarType
    frame: CoordinateFrame


def test_simple_generic():
    @dataclasses.dataclass
    class SimpleGeneric:
        point_continuous: Point3[float]
        point_discrete: Point3[int]

    parsed_instance = dcargs.parse(
        SimpleGeneric,
        args=[
            "--point-continuous.x",
            "1.2",
            "--point-continuous.y",
            "2.2",
            "--point-continuous.z",
            "3.2",
            "--point-continuous.frame",
            "WORLD",
            "--point-discrete.x",
            "1",
            "--point-discrete.y",
            "2",
            "--point-discrete.z",
            "3",
            "--point-discrete.frame",
            "WORLD",
        ],
    )
    assert parsed_instance == SimpleGeneric(
        Point3(1.2, 2.2, 3.2, CoordinateFrame.WORLD),
        Point3(1, 2, 3, CoordinateFrame.WORLD),
    )
    _check_serialization_identity(SimpleGeneric, parsed_instance)

    with pytest.raises(SystemExit):
        # Accidentally pass in floats instead of ints for discrete
        dcargs.parse(
            SimpleGeneric,
            args=[
                "--point-continuous.x",
                "1.2",
                "--point-continuous.y",
                "2.2",
                "--point-continuous.z",
                "3.2",
                "--point-continuous.frame",
                "WORLD",
                "--point-discrete.x",
                "1.5",
                "--point-discrete.y",
                "2.5",
                "--point-discrete.z",
                "3.5",
                "--point-discrete.frame",
                "WORLD",
            ],
        )


def test_multilevel_generic():
    @dataclasses.dataclass
    class Triangle(Generic[ScalarType]):
        a: Point3[ScalarType]
        b: Point3[ScalarType]
        c: Point3[ScalarType]

    parsed_instance = dcargs.parse(
        Triangle[float],
        args=[
            "--a.x",
            "1.0",
            "--a.y",
            "1.2",
            "--a.z",
            "1.3",
            "--a.frame",
            "WORLD",
            "--b.x",
            "1.0",
            "--b.y",
            "1.2",
            "--b.z",
            "1.3",
            "--b.frame",
            "WORLD",
            "--c.x",
            "1.0",
            "--c.y",
            "1.2",
            "--c.z",
            "1.3",
            "--c.frame",
            "WORLD",
        ],
    )
    assert parsed_instance == Triangle(
        Point3(1.0, 1.2, 1.3, CoordinateFrame.WORLD),
        Point3(1.0, 1.2, 1.3, CoordinateFrame.WORLD),
        Point3(1.0, 1.2, 1.3, CoordinateFrame.WORLD),
    )
    _check_serialization_identity(Triangle[float], parsed_instance)


def test_generic_nested_dataclass():
    @dataclasses.dataclass
    class Child:
        a: int
        b: int

    T = TypeVar("T")

    @dataclasses.dataclass
    class DataclassGeneric(Generic[T]):
        child: T

    parsed_instance = dcargs.parse(
        DataclassGeneric[Child], args=["--child.a", "5", "--child.b", "7"]
    )
    assert parsed_instance == DataclassGeneric(Child(5, 7))
    _check_serialization_identity(DataclassGeneric[Child], parsed_instance)


def test_generic_subparsers():
    @dataclasses.dataclass
    class CommandOne:
        a: int

    @dataclasses.dataclass
    class CommandTwo:
        b: int

    T1 = TypeVar("T1")
    T2 = TypeVar("T2")

    @dataclasses.dataclass
    class Subparser(Generic[T1, T2]):
        command: Union[T1, T2]

    parsed_instance = dcargs.parse(
        Subparser[CommandOne, CommandTwo], args="command-one --a 5".split(" ")
    )
    assert parsed_instance == Subparser(CommandOne(5))
    _check_serialization_identity(Subparser[CommandOne, CommandTwo], parsed_instance)

    parsed_instance = dcargs.parse(
        Subparser[CommandOne, CommandTwo], args="command-two --b 7".split(" ")
    )
    assert parsed_instance == Subparser(CommandTwo(7))
    _check_serialization_identity(Subparser[CommandOne, CommandTwo], parsed_instance)


def test_generic_subparsers_in_container():
    T = TypeVar("T")

    @dataclasses.dataclass
    class Command(Generic[T]):
        a: List[T]

    T1 = TypeVar("T1")
    T2 = TypeVar("T2")

    @dataclasses.dataclass
    class Subparser(Generic[T1, T2]):
        command: Union[T1, T2]

    parsed_instance = dcargs.parse(
        Subparser[Command[int], Command[float]], args="command-int --a 5 3".split(" ")
    )
    assert parsed_instance == Subparser(Command([5, 3])) and isinstance(
        parsed_instance.command.a[0], int
    )
    _check_serialization_identity(
        Subparser[Command[int], Command[float]], parsed_instance
    )

    parsed_instance = dcargs.parse(
        Subparser[Command[int], Command[float]], args="command-float --a 7 2".split(" ")
    )
    assert parsed_instance == Subparser(Command([7.0, 2.0])) and isinstance(
        parsed_instance.command.a[0], float
    )
    _check_serialization_identity(
        Subparser[Command[int], Command[float]], parsed_instance
    )


# Not implemented. It's unclear whether this is feasible, because generics are lost in
# the mro: https://github.com/python/typing/issues/777
#
# def test_generic_inherited():
#     class UnrelatedParentClass:
#         pass
#
#     T = TypeVar("T")
#
#     @dataclasses.dataclass
#     class ActualParentClass(Generic[T]):
#         x: T  # Documentation 1
#
#         # Documentation 2
#         y: T
#
#         z: T = 3
#         """Documentation 3"""
#
#     @dataclasses.dataclass
#     class ChildClass(UnrelatedParentClass, ActualParentClass[int]):
#         pass
#
#     assert dcargs.parse(ChildClass, args=["--x", 1, "--y", 2, "--z", 3]) == ChildClass(
#         1, 2, 3
#     )
