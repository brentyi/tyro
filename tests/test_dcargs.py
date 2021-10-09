import dataclasses
import enum
import io
import pathlib
from contextlib import redirect_stdout
from typing import ClassVar, List, Optional, Sequence, Tuple, Union

import pytest
from typing_extensions import Annotated, Final, Literal  # Backward compat

import dcargs


def test_basic():
    @dataclasses.dataclass
    class ManyTypes:
        i: int
        s: str
        f: float
        p: pathlib.Path

    assert (
        dcargs.parse(
            ManyTypes,
            args=[
                "--i",
                "5",
                "--s",
                "5",
                "--f",
                "5",
                "--p",
                "~",
            ],
        )
        == ManyTypes(i=5, s="5", f=5.0, p=pathlib.Path("~"))
    )


def test_required():
    @dataclasses.dataclass
    class A:
        x: int

    with pytest.raises(SystemExit):
        dcargs.parse(A, args=[])


def test_flag():
    """When boolean flags have no default value, they must be explicitly specified."""

    @dataclasses.dataclass
    class A:
        x: bool

    with pytest.raises(SystemExit):
        dcargs.parse(A, args=[])

    assert dcargs.parse(A, args=["--x", "1"]) == A(True)
    assert dcargs.parse(A, args=["--x", "true"]) == A(True)
    assert dcargs.parse(A, args=["--x", "True"]) == A(True)

    assert dcargs.parse(A, args=["--x", "0"]) == A(False)
    assert dcargs.parse(A, args=["--x", "false"]) == A(False)
    assert dcargs.parse(A, args=["--x", "False"]) == A(False)


def test_flag_default_false():
    """When boolean flags default to False, a --flag-name flag must be passed in to flip it to True."""

    @dataclasses.dataclass
    class A:
        x: bool = False

    assert dcargs.parse(A, args=[]) == A(False)
    assert dcargs.parse(A, args=["--x"]) == A(True)


def test_flag_default_true():
    """When boolean flags default to True, a --no-flag-name flag must be passed in to flip it to False."""

    @dataclasses.dataclass
    class A:
        x: bool = True

    assert dcargs.parse(A, args=[]) == A(True)
    assert dcargs.parse(A, args=["--no-x"]) == A(False)


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


def test_sequences():
    @dataclasses.dataclass
    class A:
        x: Sequence[int]

    assert dcargs.parse(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=[])


def test_lists():
    @dataclasses.dataclass
    class A:
        x: List[int]

    assert dcargs.parse(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=[])


def test_optional_sequences():
    @dataclasses.dataclass
    class A:
        x: Optional[Sequence[int]]

    assert dcargs.parse(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    assert dcargs.parse(A, args=[]) == A(x=None)


def test_optional_lists():
    @dataclasses.dataclass
    class A:
        x: Optional[List[int]]

    assert dcargs.parse(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    assert dcargs.parse(A, args=[]) == A(x=None)


def test_tuples_fixed():
    @dataclasses.dataclass
    class A:
        x: Tuple[int, int, int]

    assert dcargs.parse(A, args=["--x", "1", "2", "3"]) == A(x=(1, 2, 3))
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=[])


def test_tuples_variable():
    @dataclasses.dataclass
    class A:
        x: Tuple[int, ...]

    assert dcargs.parse(A, args=["--x", "1", "2", "3"]) == A(x=(1, 2, 3))
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=[])


def test_tuples_variable_optional():
    @dataclasses.dataclass
    class A:
        x: Optional[Tuple[int, ...]]

    assert dcargs.parse(A, args=["--x", "1", "2", "3"]) == A(x=(1, 2, 3))
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
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


def test_optional_literal():
    @dataclasses.dataclass
    class A:
        x: Optional[Literal[0, 1, 2]]

    assert dcargs.parse(A, args=["--x", "1"]) == A(x=1)
    with pytest.raises(SystemExit):
        assert dcargs.parse(A, args=["--x", "3"])
    assert dcargs.parse(A, args=[]) == A(x=None)


def test_annotated():
    """Annotated[] is a no-op."""

    @dataclasses.dataclass
    class A:
        x: Annotated[int, "some label"] = 3

    assert dcargs.parse(A, args=["--x", "5"]) == A(x=5)


def test_annotated_optional():
    """Annotated[] is a no-op."""

    @dataclasses.dataclass
    class A:
        x: Annotated[Optional[int], "some label"] = 3

    assert dcargs.parse(A, args=[]) == A(x=3)
    assert dcargs.parse(A, args=["--x", "5"]) == A(x=5)


def test_optional_annotated():
    """Annotated[] is a no-op."""

    @dataclasses.dataclass
    class A:
        x: Optional[Annotated[int, "some label"]] = 3

    assert dcargs.parse(A, args=[]) == A(x=3)
    assert dcargs.parse(A, args=["--x", "5"]) == A(x=5)


def test_final():
    """Final[] is a no-op."""

    @dataclasses.dataclass
    class A:
        x: Final[int] = 3

    assert dcargs.parse(A, args=["--x", "5"]) == A(x=5)


def test_final_optional():
    @dataclasses.dataclass
    class A:
        x: Final[Optional[int]] = 3

    assert dcargs.parse(A, args=[]) == A(x=3)
    assert dcargs.parse(A, args=["--x", "5"]) == A(x=5)


def test_classvar():
    """ClassVar[] types should be skipped."""

    @dataclasses.dataclass
    class A:
        x: ClassVar[int] = 5

    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x", "1"])
    assert dcargs.parse(A, args=[]) == A()


def test_nested():
    @dataclasses.dataclass
    class B:
        y: int

    @dataclasses.dataclass
    class A:
        x: int
        b: B

    assert dcargs.parse(A, args=["--x", "1", "--b.y", "3"]) == A(x=1, b=B(y=3))


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


def test_optional_subparser():
    @dataclasses.dataclass
    class B:
        y: int

    @dataclasses.dataclass
    class C:
        z: int

    @dataclasses.dataclass
    class A:
        x: int
        bc: Optional[Union[B, C]]

    assert dcargs.parse(A, args=["--x", "1", "B", "--y", "3"]) == A(x=1, bc=B(y=3))
    assert dcargs.parse(A, args=["--x", "1", "C", "--z", "3"]) == A(x=1, bc=C(z=3))
    assert dcargs.parse(A, args=["--x", "1"]) == A(x=1, bc=None)

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

        z: int = 3
        """Documentation 3"""

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with redirect_stdout(f):
            dcargs.parse(Helptext, args=["--help"])
    helptext = f.getvalue()
    assert "--x INT     Documentation 1\n" in helptext
    assert "--y INT     Documentation 2\n" in helptext
    assert "--z INT     Documentation 3 (default: 3)\n" in helptext
