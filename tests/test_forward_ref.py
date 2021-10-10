import dataclasses
from typing import Union

import pytest

import dcargs


@dataclasses.dataclass
class A1:
    x: int
    bc: "Union[B, C]"


@dataclasses.dataclass
class A2:
    x: int
    bc: Union["B", "C"]


@dataclasses.dataclass
class B:
    y: "int"


@dataclasses.dataclass
class C:
    z: int


def test_forward_ref_1():

    assert dcargs.parse(A1, args=["--x", "1", "B", "--y", "3"]) == A1(x=1, bc=B(y=3))
    assert dcargs.parse(A1, args=["--x", "1", "C", "--z", "3"]) == A1(x=1, bc=C(z=3))

    with pytest.raises(SystemExit):
        dcargs.parse(A1, args=["--x", "1", "B", "--z", "3"])
    with pytest.raises(SystemExit):
        dcargs.parse(A1, args=["--x", "1", "C", "--y", "3"])


def test_forward_ref_2():

    assert dcargs.parse(A2, args=["--x", "1", "B", "--y", "3"]) == A2(x=1, bc=B(y=3))
    assert dcargs.parse(A2, args=["--x", "1", "C", "--z", "3"]) == A2(x=1, bc=C(z=3))

    with pytest.raises(SystemExit):
        dcargs.parse(A2, args=["--x", "1", "B", "--z", "3"])
    with pytest.raises(SystemExit):
        dcargs.parse(A2, args=["--x", "1", "C", "--y", "3"])
