"""Example of parsing for generic dataclasses.

Usage:
`python ./14_generics.py --help`
"""

import dataclasses
from typing import Generic, TypeVar

import dcargs

ScalarType = TypeVar("ScalarType")
ShapeType = TypeVar("ShapeType")


@dataclasses.dataclass(frozen=True)
class Point3(Generic[ScalarType]):
    x: ScalarType
    y: ScalarType
    z: ScalarType
    frame_id: str


@dataclasses.dataclass(frozen=True)
class Triangle:
    a: Point3[float]
    b: Point3[float]
    c: Point3[float]


@dataclasses.dataclass(frozen=True)
class Args(Generic[ShapeType]):
    point_continuous: Point3[float]
    point_discrete: Point3[int]
    shape: ShapeType


if __name__ == "__main__":
    args = dcargs.cli(Args[Triangle])
    print(args)
