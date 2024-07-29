# mypy: ignore-errors
#
# PEP 695 isn't yet supported in mypy. (April 4, 2024)
"""Generic Types (Python 3.12+ syntax)

Example of parsing for generic dataclasses using syntax introduced in Python
3.12 (`PEP 695 <https://peps.python.org/pep-0695/>`_).

.. warning::
    If used in conjunction with :code:`from __future__ import annotations`, the updated type parameter syntax requires Python 3.12.4 or newer. For technical details, see `this CPython PR <https://github.com/python/cpython/pull/118009>`_.

Usage:
`python ./05_generics.py --help`
"""

import dataclasses

import tyro


@dataclasses.dataclass(frozen=True)
class Point3[ScalarType: (int, float)]:
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
