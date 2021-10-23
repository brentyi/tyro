import dataclasses
import enum
import pathlib
from typing import ClassVar, List, Optional, Sequence, Tuple, Union

import pytest
from typing_extensions import Annotated, Final, Literal  # Backward compatibility.

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


def test_flag_default_true_nested():
    """When boolean flags default to True, a --no-flag-name flag must be passed in to flip it to False."""

    @dataclasses.dataclass
    class NestedDefaultTrue:
        x: bool = True

    @dataclasses.dataclass
    class A:
        x: NestedDefaultTrue

    assert dcargs.parse(A, args=[]) == A(NestedDefaultTrue(True))
    assert dcargs.parse(A, args=["--x.no-x"]) == A(NestedDefaultTrue(False))


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


# TODO: implement this!
# def test_optional_nested():
#     @dataclasses.dataclass
#     class OptionalNestedChild:
#         y: int
#         z: int
#
#     @dataclasses.dataclass
#     class OptionalNested:
#         x: int
#         b: Optional[OptionalNestedChild]
#
#     assert dcargs.parse(OptionalNested, args=["--x", "1"]) == OptionalNested(
#         x=1, b=None
#     )
#     with pytest.raises(SystemExit):
#         dcargs.parse(OptionalNested, args=["--x", "1", "--b.y", "3"])
#     with pytest.raises(SystemExit):
#         dcargs.parse(OptionalNested, args=["--x", "1", "--b.z", "3"])
#
#     assert dcargs.parse(
#         OptionalNested, args=["--x", "1", "--b.y", "2", "--b.z", "3"]
#     ) == OptionalNested(x=1, b=OptionalNestedChild(y=2, z=3))


def test_subparser():
    @dataclasses.dataclass
    class HTTPServer:
        y: int

    @dataclasses.dataclass
    class SMTPServer:
        z: int

    @dataclasses.dataclass
    class Subparser:
        x: int
        bc: Union[HTTPServer, SMTPServer]

    assert dcargs.parse(
        Subparser, args=["--x", "1", "http-server", "--y", "3"]
    ) == Subparser(x=1, bc=HTTPServer(y=3))
    assert dcargs.parse(
        Subparser, args=["--x", "1", "smtp-server", "--z", "3"]
    ) == Subparser(x=1, bc=SMTPServer(z=3))

    with pytest.raises(SystemExit):
        dcargs.parse(Subparser, args=["--x", "1", "b", "--z", "3"])
    with pytest.raises(SystemExit):
        dcargs.parse(Subparser, args=["--x", "1", "c", "--y", "3"])


def test_optional_subparser():
    @dataclasses.dataclass
    class OptionalHTTPServer:
        y: int

    @dataclasses.dataclass
    class OptionalSMTPServer:
        z: int

    @dataclasses.dataclass
    class OptionalSubparser:
        x: int
        bc: Optional[Union[OptionalHTTPServer, OptionalSMTPServer]]

    assert dcargs.parse(
        OptionalSubparser, args=["--x", "1", "optional-http-server", "--y", "3"]
    ) == OptionalSubparser(x=1, bc=OptionalHTTPServer(y=3))
    assert dcargs.parse(
        OptionalSubparser, args=["--x", "1", "optional-smtp-server", "--z", "3"]
    ) == OptionalSubparser(x=1, bc=OptionalSMTPServer(z=3))
    assert dcargs.parse(OptionalSubparser, args=["--x", "1"]) == OptionalSubparser(
        x=1, bc=None
    )

    with pytest.raises(SystemExit):
        dcargs.parse(OptionalSubparser, args=["--x", "1", "B", "--z", "3"])
    with pytest.raises(SystemExit):
        dcargs.parse(OptionalSubparser, args=["--x", "1", "C", "--y", "3"])


def test_parse_empty_description():
    """If the file has no dosctring, it should be treated as an empty string."""

    @dataclasses.dataclass
    class A:
        x: int = 0

    assert dcargs.parse(A, description=None) == A(x=0)
