import argparse
import copy
import dataclasses
import enum
import pathlib
from typing import (
    Any,
    AnyStr,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

import pytest
import torch
from typing_extensions import Annotated, Final, Literal, TypeAlias

import dcargs


def test_no_args():
    def main() -> int:
        return 5

    assert dcargs.cli(main, args=[]) == 5
    with pytest.raises(SystemExit):
        dcargs.cli(main, args=["3"])


def test_basic():
    @dataclasses.dataclass
    class ManyTypes:
        i: int
        s: str
        f: float
        p: pathlib.Path

    # We can directly pass a dataclass to `dcargs.cli()`:
    assert dcargs.cli(
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
    ) == ManyTypes(i=5, s="5", f=5.0, p=pathlib.Path("~"))

    # We can directly pass a function to `dcargs.cli()`:
    def function(i: int, s: str, f: float, p: pathlib.Path) -> ManyTypes:
        return ManyTypes(i=i, s=s, f=f, p=p)

    assert dcargs.cli(
        function,
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
    ) == ManyTypes(i=5, s="5", f=5.0, p=pathlib.Path("~"))

    # We can directly pass a generic class to `dcargs.cli()`:
    class Wrapper:
        def __init__(self, i: int, s: str, f: float, p: pathlib.Path):
            self.inner = ManyTypes(i=i, s=s, f=f, p=p)

    assert dcargs.cli(
        Wrapper,
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
    ).inner == ManyTypes(i=5, s="5", f=5.0, p=pathlib.Path("~"))


def test_init_false():
    @dataclasses.dataclass
    class InitFalseDataclass:
        i: int
        s: str
        f: float
        p: pathlib.Path
        ignored: str = dataclasses.field(default="hello", init=False)

    assert dcargs.cli(
        InitFalseDataclass,
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
    ) == InitFalseDataclass(i=5, s="5", f=5.0, p=pathlib.Path("~"))

    with pytest.raises(SystemExit):
        dcargs.cli(
            InitFalseDataclass,
            args=["--i", "5", "--s", "5", "--f", "5", "--p", "~", "--ignored", "blah"],
        )


def test_required():
    @dataclasses.dataclass
    class A:
        x: int

    with pytest.raises(SystemExit):
        dcargs.cli(A, args=[])


def test_flag():
    """When boolean flags have no default value, they must be explicitly specified."""

    @dataclasses.dataclass
    class A:
        x: bool

    with pytest.raises(SystemExit):
        dcargs.cli(A, args=[])

    with pytest.raises(SystemExit):
        dcargs.cli(A, args=["--x", "1"])
    with pytest.raises(SystemExit):
        dcargs.cli(A, args=["--x", "true"])
    assert dcargs.cli(A, args=["--x", "True"]) == A(True)

    with pytest.raises(SystemExit):
        dcargs.cli(A, args=["--x", "0"])
    with pytest.raises(SystemExit):
        dcargs.cli(A, args=["--x", "false"])
    assert dcargs.cli(A, args=["--x", "False"]) == A(False)


def test_flag_default_false():
    """When boolean flags default to False, a --flag-name flag must be passed in to flip it to True."""

    @dataclasses.dataclass
    class A:
        x: bool = False

    assert dcargs.cli(A, args=[]) == A(False)
    assert dcargs.cli(A, args=["--x"]) == A(True)


def test_flag_default_true():
    """When boolean flags default to True, a --no-flag-name flag must be passed in to flip it to False."""

    @dataclasses.dataclass
    class A:
        x: bool = True

    assert dcargs.cli(A, args=[]) == A(True)
    assert dcargs.cli(A, args=["--no-x"]) == A(False)


def test_flag_default_true_nested():
    """When boolean flags default to True, a --no-flag-name flag must be passed in to flip it to False."""

    @dataclasses.dataclass
    class NestedDefaultTrue:
        x: bool = True

    @dataclasses.dataclass
    class A:
        x: NestedDefaultTrue

    assert dcargs.cli(A, args=[]) == A(NestedDefaultTrue(True))
    assert dcargs.cli(A, args=["--x.no-x"]) == A(NestedDefaultTrue(False))


def test_default():
    @dataclasses.dataclass
    class A:
        x: int = 5

    assert dcargs.cli(A, args=[]) == A()


def test_default_factory():
    @dataclasses.dataclass
    class A:
        x: int = dataclasses.field(default_factory=lambda: 5)

    assert dcargs.cli(A, args=[]) == A()


def test_optional():
    @dataclasses.dataclass
    class A:
        x: Optional[int] = None

    assert dcargs.cli(A, args=[]) == A(x=None)


def test_union_basic():
    def main(x: Union[int, str]) -> Union[int, str]:
        return x

    assert dcargs.cli(main, args=["--x", "5"]) == 5
    assert dcargs.cli(main, args=["--x", "6"]) == 6
    assert dcargs.cli(main, args=["--x", "five"]) == "five"


def test_union_with_list():
    def main(x: Union[int, str, List[bool]]) -> Any:
        return x

    assert dcargs.cli(main, args=["--x", "5"]) == 5
    assert dcargs.cli(main, args=["--x", "6"]) == 6
    assert dcargs.cli(main, args=["--x", "five"]) == "five"
    assert dcargs.cli(main, args=["--x", "True"]) == "True"
    assert dcargs.cli(main, args=["--x", "True", "False"]) == [True, False]


def test_union_literal():
    def main(x: Union[Literal[1, 2], Literal[3, 4, 5], str]) -> Union[int, str]:
        return x

    assert dcargs.cli(main, args=["--x", "5"]) == 5
    assert dcargs.cli(main, args=["--x", "6"]) == "6"
    assert dcargs.cli(main, args=["--x", "five"]) == "five"


def test_func_typevar():
    T = TypeVar("T", int, str)

    def main(x: T) -> T:
        return x

    assert dcargs.cli(main, args=["--x", "5"]) == 5
    assert dcargs.cli(main, args=["--x", "five"]) == "five"


def test_func_typevar_bound():
    T = TypeVar("T", bound=int)

    def main(x: T) -> T:
        return x

    assert dcargs.cli(main, args=["--x", "5"]) == 5
    with pytest.raises(SystemExit):
        dcargs.cli(main, args=["--x", "five"])


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

    assert dcargs.cli(EnumClassA, args=["--color", "RED"]) == EnumClassA(
        color=Color.RED
    )
    assert dcargs.cli(EnumClassB, args=[]) == EnumClassB()


def test_literal():
    @dataclasses.dataclass
    class A:
        x: Literal[0, 1, 2]

    assert dcargs.cli(A, args=["--x", "1"]) == A(x=1)
    with pytest.raises(SystemExit):
        assert dcargs.cli(A, args=["--x", "3"])


def test_literal_bool():
    def main(x: Literal[True]) -> bool:
        return x

    assert dcargs.cli(main, args=["--x", "True"]) is True
    with pytest.raises(SystemExit):
        dcargs.cli(main, args=["--x", "False"])

    def main2(x: Literal[True, False]) -> bool:
        return x

    assert dcargs.cli(main2, args=["--x", "True"]) is True
    assert dcargs.cli(main2, args=["--x", "False"]) is False
    with pytest.raises(SystemExit):
        dcargs.cli(main2, args=["--x", "Tru"])


def test_literal_enum():
    class Color(enum.Enum):
        RED = enum.auto()
        GREEN = enum.auto()
        BLUE = enum.auto()

    @dataclasses.dataclass
    class A:
        x: Literal[Color.RED, Color.GREEN]

    assert dcargs.cli(A, args=["--x", "RED"]) == A(x=Color.RED)
    assert dcargs.cli(A, args=["--x", "GREEN"]) == A(x=Color.GREEN)
    with pytest.raises(SystemExit):
        assert dcargs.cli(A, args=["--x", "BLUE"])


def test_optional_literal():
    @dataclasses.dataclass
    class A:
        x: Optional[Literal[0, 1, 2]] = None

    assert dcargs.cli(A, args=["--x", "1"]) == A(x=1)
    with pytest.raises(SystemExit):
        assert dcargs.cli(A, args=["--x", "3"])
    assert dcargs.cli(A, args=[]) == A(x=None)


def test_multitype_literal():
    def main(x: Literal[0, "5"]) -> Any:
        return x

    assert dcargs.cli(main, args=["--x", "0"]) == 0
    assert dcargs.cli(main, args=["--x", "5"]) == "5"
    with pytest.raises(SystemExit):
        dcargs.cli(main, args=["--x", "6"])


def test_annotated():
    """Annotated[] is a no-op."""

    @dataclasses.dataclass
    class A:
        x: Annotated[int, "some label"] = 3

    assert dcargs.cli(A, args=["--x", "5"]) == A(x=5)


def test_annotated_optional():
    """Annotated[] is a no-op."""

    @dataclasses.dataclass
    class A:
        x: Annotated[Optional[int], "some label"] = 3

    assert dcargs.cli(A, args=[]) == A(x=3)
    assert dcargs.cli(A, args=["--x", "5"]) == A(x=5)


def test_optional_annotated():
    """Annotated[] is a no-op."""

    @dataclasses.dataclass
    class A:
        x: Optional[Annotated[int, "some label"]] = 3

    assert dcargs.cli(A, args=[]) == A(x=3)
    assert dcargs.cli(A, args=["--x", "5"]) == A(x=5)


def test_final():
    """Final[] is a no-op."""

    @dataclasses.dataclass
    class A:
        x: Final[int] = 3

    assert dcargs.cli(A, args=["--x", "5"]) == A(x=5)


def test_final_optional():
    @dataclasses.dataclass
    class A:
        x: Final[Optional[int]] = 3

    assert dcargs.cli(A, args=[]) == A(x=3)
    assert dcargs.cli(A, args=["--x", "5"]) == A(x=5)


def test_classvar():
    """ClassVar[] types should be skipped."""

    @dataclasses.dataclass
    class A:
        x: ClassVar[int] = 5

    with pytest.raises(SystemExit):
        dcargs.cli(A, args=["--x", "1"])
    assert dcargs.cli(A, args=[]) == A()


def test_parse_empty_description():
    """If the file has no dosctring, it should be treated as an empty string."""

    @dataclasses.dataclass
    class A:
        x: int = 0

    assert dcargs.cli(A, description=None, args=[]) == A(x=0)


SomeTypeAlias: TypeAlias = int


def test_type_alias():
    def add(a: SomeTypeAlias, b: SomeTypeAlias) -> SomeTypeAlias:
        return a + b

    assert dcargs.cli(add, args=["--a", "5", "--b", "7"]) == 12


@pytest.mark.filterwarnings("ignore::Warning")
def test_any():
    def main(x: Any = 5) -> Any:
        return x

    assert dcargs.cli(main, args=[]) == 5


def test_bytes():
    def main(x: bytes) -> bytes:
        return x

    assert dcargs.cli(main, args=["--x", "hello"]) == b"hello"


def test_any_str():
    def main(x: AnyStr) -> AnyStr:
        return x

    # Use bytes when provided ascii-compatible inputs.
    assert dcargs.cli(main, args=["--x", "hello"]) == b"hello"
    assert dcargs.cli(main, args=["--x", "hello„"]) == "hello„"


def test_fixed():
    def main(x: Callable[[int], int] = lambda x: x * 2) -> Callable[[int], int]:
        return x

    assert dcargs.cli(main, args=[])(3) == 6
    with pytest.raises(SystemExit):
        dcargs.cli(main, args=["--x", "something"])


def test_fixed_dataclass_type():
    @dataclasses.dataclass
    class Dummy:
        pass

    def main(x: Callable = Dummy) -> Callable:
        return x

    assert dcargs.cli(main, args=[]) is Dummy
    with pytest.raises(SystemExit):
        dcargs.cli(main, args=["--x", "something"])


def test_missing_singleton():
    assert dcargs.MISSING is copy.deepcopy(dcargs.MISSING)


def test_torch_device():
    def main(device: torch.device) -> torch.device:
        return device

    assert dcargs.cli(main, args=["--device", "cpu"]) == torch.device("cpu")


def test_torch_device_2():
    assert dcargs.cli(torch.device, args=["cpu"]) == torch.device("cpu")


def test_just_int():
    assert dcargs.cli(int, args=["123"]) == 123


def test_just_dict():
    assert dcargs.cli(Dict[str, str], args="key value key2 value2".split(" ")) == {
        "key": "value",
        "key2": "value2",
    }


def test_just_list():
    assert dcargs.cli(List[int], args="1 2 3 4".split(" ")) == [1, 2, 3, 4]


def test_just_tuple():
    assert dcargs.cli(Tuple[int, int, int, int], args="1 2 3 4".split(" ")) == (
        1,
        2,
        3,
        4,
    )


def test_return_parser():
    def main() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser()
        return parser

    assert isinstance(dcargs.cli(main, args=[]), argparse.ArgumentParser)
