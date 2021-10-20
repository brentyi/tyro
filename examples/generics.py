import dataclasses
from typing import Generic, Optional, TypeVar

import dcargs

ScalarType = TypeVar("ScalarType")


@dataclasses.dataclass
class Point3(Generic[ScalarType]):
    x: ScalarType
    y: ScalarType
    z: ScalarType
    frame_id: str


@dataclasses.dataclass
class Triangle(Generic[ScalarType]):
    a: Point3[ScalarType]
    b: Point3[ScalarType]
    c: Point3[ScalarType]


@dataclasses.dataclass
class Args:
    point_continuous: Point3[float]
    point_discrete: Point3[int]

    triangle_continuous: Triangle[float]
    triangle_discrete: Triangle[int]

    triangle_optional_coords: Triangle[Optional[float]]


if __name__ == "__main__":
    args = dcargs.parse(Args)
    print(args)
