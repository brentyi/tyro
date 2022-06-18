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

    assert dcargs.cli(A1, args=["--x", "1", "b", "--y", "3"]) == A1(x=1, bc=B(y=3))
    assert dcargs.cli(A1, args=["--x", "1", "c", "--z", "3"]) == A1(x=1, bc=C(z=3))

    with pytest.raises(SystemExit):
        dcargs.cli(A1, args=["--x", "1", "b", "--z", "3"])
    with pytest.raises(SystemExit):
        dcargs.cli(A1, args=["--x", "1", "c", "--y", "3"])


def test_forward_ref_2():

    assert dcargs.cli(A2, args=["--x", "1", "b", "--y", "3"]) == A2(x=1, bc=B(y=3))
    assert dcargs.cli(A2, args=["--x", "1", "c", "--z", "3"]) == A2(x=1, bc=C(z=3))

    with pytest.raises(SystemExit):
        dcargs.cli(A2, args=["--x", "1", "b", "--z", "3"])
    with pytest.raises(SystemExit):
        dcargs.cli(A2, args=["--x", "1", "c", "--y", "3"])
