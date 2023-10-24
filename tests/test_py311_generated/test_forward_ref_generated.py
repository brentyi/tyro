import dataclasses
from typing import Union

import pytest

import tyro


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
    assert tyro.cli(A1, args=["--x", "1", "bc:b", "--bc.y", "3"]) == A1(x=1, bc=B(y=3))
    assert tyro.cli(A1, args=["--x", "1", "bc:c", "--bc.z", "3"]) == A1(x=1, bc=C(z=3))

    with pytest.raises(SystemExit):
        tyro.cli(A1, args=["--x", "1", "bc:b", "--bc.z", "3"])
    with pytest.raises(SystemExit):
        tyro.cli(A1, args=["--x", "1", "bc:c", "--bc.y", "3"])


def test_forward_ref_2():
    assert tyro.cli(A2, args=["--x", "1", "bc:b", "--bc.y", "3"]) == A2(x=1, bc=B(y=3))
    assert tyro.cli(A2, args=["--x", "1", "bc:c", "--bc.z", "3"]) == A2(x=1, bc=C(z=3))

    with pytest.raises(SystemExit):
        tyro.cli(A2, args=["--x", "1", "bc:b", "--bc.z", "3"])
    with pytest.raises(SystemExit):
        tyro.cli(A2, args=["--x", "1", "bc:c", "--bc.y", "3"])
