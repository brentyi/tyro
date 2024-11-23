"""Generics (Python <3.12)

The legacy :py:class:`typing.Generic` and :py:class:`typing.TypeVar` syntax for
generic types is also supported.

Usage:

    python ./02_generics.py --help
"""

import dataclasses
from typing import Generic, TypeVar

import tyro

ScalarType = TypeVar("ScalarType", int, float)
ShapeType = TypeVar("ShapeType")


@dataclasses.dataclass
class Point3(Generic[ScalarType]):
    x: ScalarType
    y: ScalarType
    z: ScalarType
    frame_id: str


@dataclasses.dataclass
class Triangle:
    a: Point3[float]
    b: Point3[float]
    c: Point3[float]


@dataclasses.dataclass
class Args(Generic[ShapeType]):
    shape: ShapeType


if __name__ == "__main__":
    args = tyro.cli(Args[Triangle])
    print(args)
