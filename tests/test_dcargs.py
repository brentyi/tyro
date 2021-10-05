import dataclasses
import enum
import io
from contextlib import redirect_stdout
from typing import Optional, Union

import pytest
from typing_extensions import Literal  # Python 3.7 compat

import dcargs


def test_basic():
    @dataclasses.dataclass
    class A:
        x: int

    assert dcargs.parse(A, args=["--x", "5"]) == A(x=5)


def test_required():
    @dataclasses.dataclass
    class A:
        x: int

    with pytest.raises(SystemExit):
        dcargs.parse(A, args=[])


def test_flag():
    @dataclasses.dataclass
    class A:
        x: bool

    assert dcargs.parse(A, args=[]) == A(False)
    assert dcargs.parse(A, args=["--x"]) == A(True)


def test_flag_inv():
    # This is a weird but currently expected behavior: the default values of boolean
    # flags are ignored. Should think harder about how this is handled.
    @dataclasses.dataclass
    class A:
        x: bool = True

    assert dcargs.parse(A, args=[]) == A(False)
    assert dcargs.parse(A, args=["--x"]) == A(True)


def test_default():
    @dataclasses.dataclass
    class A:
        x: int = 5

    assert dcargs.parse(A, args=[]) == A()


def test_optional():
    @dataclasses.dataclass
    class A:
        x: Optional[int]

    assert dcargs.parse(A, args=[]) == A(x=None)


def test_enum():
    class Color(enum.Enum):
        RED = enum.auto()
        GREEN = enum.auto()
        BLUE = enum.auto()

    @dataclasses.dataclass
    class EnumClassA:
        color: Color

    @dataclasses.dataclass
    class EnumClassB:
        color: Color = Color.GREEN

    assert dcargs.parse(EnumClassA, args=["--color", "RED"]) == EnumClassA(
        color=Color.RED
    )
    assert dcargs.parse(EnumClassB) == EnumClassB()


def test_literal():
    @dataclasses.dataclass
    class A:
        x: Literal[0, 1, 2]

    assert dcargs.parse(A, args=["--x", "1"]) == A(x=1)
    with pytest.raises(SystemExit):
        assert dcargs.parse(A, args=["--x", "3"])


def test_nested():
    @dataclasses.dataclass
    class B:
        y: int

    @dataclasses.dataclass
    class A:
        x: int
        b: B

    assert dcargs.parse(A, args=["--x", "1", "--b-y", "3"]) == A(x=1, b=B(y=3))


def test_subparser():
    @dataclasses.dataclass
    class B:
        y: int

    @dataclasses.dataclass
    class C:
        z: int

    @dataclasses.dataclass
    class A:
        x: int
        bc: Union[B, C]

    assert dcargs.parse(A, args=["--x", "1", "B", "--y", "3"]) == A(x=1, bc=B(y=3))
    assert dcargs.parse(A, args=["--x", "1", "C", "--z", "3"]) == A(x=1, bc=C(z=3))

    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x", "1", "B", "--z", "3"])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x", "1", "C", "--y", "3"])


def test_helptext():
    @dataclasses.dataclass
    class Helptext:
        x: int  # Documentation 1

        # Documentation 2
        y: int

        z: int
        """Documentation 3"""

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with redirect_stdout(f):
            dcargs.parse(Helptext, args=["--help"])
    helptext = f.getvalue()
    assert "--x X       Documentation 1 (int)" in helptext
    assert "--y Y       Documentation 2 (int)" in helptext
    assert "--z Z       Documentation 3 (int)" in helptext
