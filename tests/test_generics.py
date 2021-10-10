import dataclasses
from typing import Generic, TypeVar

import pytest

import dcargs

ScalarType = TypeVar("ScalarType")


@dataclasses.dataclass
class Point3(Generic[ScalarType]):
    x: ScalarType
    y: ScalarType
    z: ScalarType
    frame_id: str


def test_simple_generic():
    @dataclasses.dataclass
    class SimpleGeneric:
        point_continuous: Point3[float]
        point_discrete: Point3[int]

    assert (
        dcargs.parse(
            SimpleGeneric,
            args=[
                "--point-continuous.x",
                "1.2",
                "--point-continuous.y",
                "2.2",
                "--point-continuous.z",
                "3.2",
                "--point-continuous.frame-id",
                "world",
                "--point-discrete.x",
                "1",
                "--point-discrete.y",
                "2",
                "--point-discrete.z",
                "3",
                "--point-discrete.frame-id",
                "world",
            ],
        )
        == SimpleGeneric(Point3(1.2, 2.2, 3.2, "world"), Point3(1, 2, 3, "world"))
    )

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
                "--point-continuous.frame-id",
                "world",
                "--point-discrete.x",
                "1.5",
                "--point-discrete.y",
                "2.5",
                "--point-discrete.z",
                "3.5",
                "--point-discrete.frame-id",
                "world",
            ],
        )


def test_multilevel_generic():
    @dataclasses.dataclass
    class Triangle(Generic[ScalarType]):
        a: Point3[ScalarType]
        b: Point3[ScalarType]
        c: Point3[ScalarType]

    dcargs.parse(
        Triangle[float],
        args=[
            "--a.x",
            "1.0",
            "--a.y",
            "1.2",
            "--a.z",
            "1.3",
            "--a.frame-id",
            "world",
            "--b.x",
            "1.0",
            "--b.y",
            "1.2",
            "--b.z",
            "1.3",
            "--b.frame-id",
            "world",
            "--c.x",
            "1.0",
            "--c.y",
            "1.2",
            "--c.z",
            "1.3",
            "--c.frame-id",
            "world",
        ],
    ) == Triangle(
        Point3(1.0, 1.2, 1.3, "world"),
        Point3(1.0, 1.2, 1.3, "world"),
        Point3(1.0, 1.2, 1.3, "world"),
    )
