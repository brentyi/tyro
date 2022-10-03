"""Example of parsing for generic dataclasses.

Usage:
`python ./14_generics.py --help`
"""

import dataclasses
from typing import Generic, TypeVar

import dcargs

ScalarType = TypeVar("ScalarType", int, float)
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
    shape: ShapeType


if __name__ == "__main__":
    args = dcargs.cli(Args[Triangle])
    print(args)