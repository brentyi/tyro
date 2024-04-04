"""Generic Types (Python 3.12+ syntax)

Example of parsing for generic dataclasses.

Usage:
`python ./05_generics.py --help`
"""

import dataclasses

import tyro


@dataclasses.dataclass(frozen=True)
class Point3[ScalarType: int | float]:
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
class Args[ShapeType]:
    shape: ShapeType


if __name__ == "__main__":
    args = tyro.cli(Args[Triangle])
    print(args)
