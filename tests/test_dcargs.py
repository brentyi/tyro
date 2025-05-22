import argparse
import copy
import dataclasses
import datetime
import enum
import os
import pathlib
from typing import (
    Any,
    AnyStr,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Text,
    Tuple,
    TypeVar,
    Union,
)

import pytest
from helptext_utils import get_helptext_with_checks
from typing_extensions import (
    Annotated,
    Final,
    Literal,
    Protocol,
    TypeAlias,
    runtime_checkable,
)

import tyro


def test_no_args() -> None:
    def main() -> int:
        return 5

    assert tyro.cli(main, args=[]) == 5
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["3"])


def test_basic() -> None:
    @dataclasses.dataclass
    class ManyTypes:
        i: int
        s: str
        f: float
        p: pathlib.Path

    # We can directly pass a dataclass to `tyro.cli()`:
    assert tyro.cli(
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

    # We can directly pass a function to `tyro.cli()`:
    def function(i: int, s: str, f: float, p: pathlib.Path) -> ManyTypes:
        return ManyTypes(i=i, s=s, f=f, p=p)

    assert tyro.cli(
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

    # We can directly pass a generic class to `tyro.cli()`:
    class Wrapper:
        def __init__(self, i: int, s: str, f: float, p: pathlib.Path):
            self.inner = ManyTypes(i=i, s=s, f=f, p=p)

    assert tyro.cli(
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


def test_init_false() -> None:
    @dataclasses.dataclass
    class InitFalseDataclass:
        i: int
        s: str
        f: float
        dir: pathlib.Path
        ignored: str = dataclasses.field(default="hello", init=False)

    assert tyro.cli(
        InitFalseDataclass,
        args=[
            "--i",
            "5",
            "--s",
            "5",
            "--f",
            "5",
            "--dir",
            "~",
        ],
    ) == InitFalseDataclass(i=5, s="5", f=5.0, dir=pathlib.Path("~"))

    with pytest.raises(SystemExit):
        tyro.cli(
            InitFalseDataclass,
            args=[
                "--i",
                "5",
                "--s",
                "5",
                "--f",
                "5",
                "--dir",
                "~",
                "--ignored",
                "blah",
            ],
        )


def test_required() -> None:
    @dataclasses.dataclass
    class A:
        x: int

    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])


def test_flag() -> None:
    """When boolean flags have no default value, they must be explicitly specified."""

    @dataclasses.dataclass
    class A:
        x: bool

    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])

    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "1"])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "true"])
    assert tyro.cli(A, args=["--x", "True"]) == A(True)

    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "0"])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "false"])
    assert tyro.cli(A, args=["--x", "False"]) == A(False)


def test_flag_default_false() -> None:
    """When boolean flags default to False, a --flag-name flag must be passed in to flip it to True."""

    @dataclasses.dataclass
    class A:
        x: bool = False

    assert tyro.cli(A, args=[]) == A(False)
    assert tyro.cli(A, args=["--x"]) == A(True)


def test_flag_default_true() -> None:
    """When boolean flags default to True, a --no-flag-name flag must be passed in to flip it to False."""

    @dataclasses.dataclass
    class A:
        x: bool = True

    assert tyro.cli(A, args=[]) == A(True)
    assert tyro.cli(A, args=["--no-x"]) == A(False)


def test_flag_default_true_nested() -> None:
    """When boolean flags default to True, a --no-flag-name flag must be passed in to flip it to False."""

    @dataclasses.dataclass
    class NestedDefaultTrue:
        x: bool = True

    @dataclasses.dataclass
    class A:
        x: NestedDefaultTrue

    assert tyro.cli(A, args=[]) == A(NestedDefaultTrue(True))
    assert tyro.cli(A, args=["--x.no-x"]) == A(NestedDefaultTrue(False))


def test_default() -> None:
    @dataclasses.dataclass
    class A:
        x: int = 5

    assert tyro.cli(A, args=[]) == A()


def test_default_factory() -> None:
    @dataclasses.dataclass
    class A:
        x: int = dataclasses.field(default_factory=lambda: 5)

    assert tyro.cli(A, args=[]) == A()


def test_optional() -> None:
    @dataclasses.dataclass
    class A:
        x: Optional[int] = None

    assert tyro.cli(A, args=[]) == A(x=None)


def test_union_basic() -> None:
    def main(x: Union[int, str]) -> Union[int, str]:
        return x

    assert tyro.cli(main, args=["--x", "5"]) == 5
    assert tyro.cli(main, args=["--x", "6"]) == 6
    assert tyro.cli(main, args=["--x", "five"]) == "five"


def test_union_with_list() -> None:
    def main(x: Union[int, str, List[bool]]) -> Any:
        return x

    assert tyro.cli(main, args=["--x", "5"]) == 5
    assert tyro.cli(main, args=["--x", "6"]) == 6
    assert tyro.cli(main, args=["--x", "five"]) == "five"
    assert tyro.cli(main, args=["--x", "True"]) == "True"
    assert tyro.cli(main, args=["--x", "True", "False"]) == [True, False]


def test_union_literal() -> None:
    def main(x: Union[Literal[1, 2], Literal[3, 4, 5], str]) -> Union[int, str]:
        return x

    assert tyro.cli(main, args=["--x", "5"]) == 5
    assert tyro.cli(main, args=["--x", "6"]) == "6"
    assert tyro.cli(main, args=["--x", "five"]) == "five"


def test_literal_bad_default() -> None:
    def main(x: Literal[1, 2] = 3) -> int:  # type: ignore
        return x

    assert tyro.cli(main, args=[]) == 3
    assert tyro.cli(main, args=["--x", "2"]) == 2
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--x", "five"])


def test_func_typevar() -> None:
    T = TypeVar("T", int, str)

    def main(x: T) -> T:
        return x

    assert tyro.cli(main, args=["--x", "5"]) == 5
    assert tyro.cli(main, args=["--x", "five"]) == "five"


def test_func_typevar_bound() -> None:
    T = TypeVar("T", bound=int)

    def main(x: T) -> T:
        return x

    assert tyro.cli(main, args=["--x", "5"]) == 5
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--x", "five"])


def test_enum() -> None:
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

    assert tyro.cli(EnumClassA, args=["--color", "RED"]) == EnumClassA(color=Color.RED)
    assert tyro.cli(EnumClassB, args=[]) == EnumClassB()
    with pytest.raises(SystemExit):
        assert tyro.cli(EnumClassA, args=["--color", "red"])


def test_enum_alias() -> None:
    class Color(enum.Enum):
        RED = 1
        ROUGE = 1

    @dataclasses.dataclass
    class A:
        color: Color

    assert tyro.cli(A, args=["--color", "RED"]) == A(color=Color.RED)
    assert tyro.cli(A, args=["--color", "ROUGE"]) == A(color=Color.ROUGE)
    assert tyro.cli(A, args=["--color", "ROUGE"]) == A(color=Color.RED)


def test_enum_values() -> None:
    class Color(enum.Enum):
        RED = "red"
        GREEN = "green"
        BLUE = "blue"

    @dataclasses.dataclass
    class EnumClassA:
        color: Annotated[Color, tyro.conf.EnumChoicesFromValues]

    @dataclasses.dataclass
    class EnumClassB:
        color: Annotated[Color, tyro.conf.EnumChoicesFromValues] = Color.GREEN

    assert tyro.cli(EnumClassA, args=["--color", "red"]) == EnumClassA(color=Color.RED)
    assert tyro.cli(EnumClassB, args=[]) == EnumClassB()
    with pytest.raises(SystemExit):
        assert tyro.cli(EnumClassA, args=["--color", "RED"])


def test_enum_values_ints() -> None:
    class Color(enum.Enum):
        RED = 0
        GREEN = 1
        BLUE = 2

    @dataclasses.dataclass
    class EnumClassA:
        color: Annotated[Color, tyro.conf.EnumChoicesFromValues]

    @dataclasses.dataclass
    class EnumClassB:
        color: Annotated[Color, tyro.conf.EnumChoicesFromValues] = Color.GREEN

    assert tyro.cli(EnumClassA, args=["--color", "0"]) == EnumClassA(color=Color.RED)
    assert tyro.cli(EnumClassB, args=[]) == EnumClassB()
    with pytest.raises(SystemExit):
        assert tyro.cli(EnumClassA, args=["--color", "red"])
    with pytest.raises(SystemExit):
        assert tyro.cli(EnumClassA, args=["--color", "RED"])


def test_literal() -> None:
    @dataclasses.dataclass
    class A:
        x: Literal[0, 1, 2]

    assert tyro.cli(A, args=["--x", "1"]) == A(x=1)
    with pytest.raises(SystemExit):
        assert tyro.cli(A, args=["--x", "3"])


def test_literal_none() -> None:
    @dataclasses.dataclass
    class A:
        x: Literal[0, 1, None, 2]

    assert tyro.cli(A, args=["--x", "1"]) == A(x=1)
    assert tyro.cli(A, args=["--x", "None"]) == A(x=None)
    with pytest.raises(SystemExit):
        assert tyro.cli(A, args=["--x", "3"])


Choices = int
Choices = tyro.extras.literal_type_from_choices([0, 1, 2])  # type: ignore


def test_dynamic_literal() -> None:
    @dataclasses.dataclass
    class A:
        x: Choices  # type: ignore

    assert tyro.cli(A, args=["--x", "1"]) == A(x=1)
    with pytest.raises(SystemExit):
        assert tyro.cli(A, args=["--x", "3"])


def test_literal_bool() -> None:
    def main(x: Literal[True]) -> bool:
        return x

    assert tyro.cli(main, args=["--x", "True"]) is True
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--x", "False"])

    def main2(x: Literal[True, False]) -> bool:
        return x

    assert tyro.cli(main2, args=["--x", "True"]) is True
    assert tyro.cli(main2, args=["--x", "False"]) is False
    with pytest.raises(SystemExit):
        tyro.cli(main2, args=["--x", "Tru"])


def test_literal_enum() -> None:
    class Color(enum.Enum):
        RED = enum.auto()
        GREEN = enum.auto()
        BLUE = enum.auto()

    @dataclasses.dataclass
    class A:
        x: Literal[Color.RED, Color.GREEN]

    assert tyro.cli(A, args=["--x", "RED"]) == A(x=Color.RED)
    assert tyro.cli(A, args=["--x", "GREEN"]) == A(x=Color.GREEN)
    with pytest.raises(SystemExit):
        assert tyro.cli(A, args=["--x", "BLUE"])
    with pytest.raises(SystemExit):
        assert tyro.cli(A, args=["--x", "red"])


def test_literal_enum_values() -> None:
    class Color(enum.Enum):
        RED = "red"
        GREEN = "green"
        BLUE = "blue"

    @dataclasses.dataclass
    class A:
        x: Annotated[
            Literal[Color.RED, Color.GREEN],
            tyro.conf.EnumChoicesFromValues,
        ]

    assert tyro.cli(A, args=["--x", "red"]) == A(x=Color.RED)
    assert tyro.cli(A, args=["--x", "green"]) == A(x=Color.GREEN)
    with pytest.raises(SystemExit):
        assert tyro.cli(A, args=["--x", "RED"])
    with pytest.raises(SystemExit):
        assert tyro.cli(A, args=["--x", "blue"])


def test_optional_literal() -> None:
    @dataclasses.dataclass
    class A:
        x: Optional[Literal[0, 1, 2]] = None

    assert tyro.cli(A, args=["--x", "1"]) == A(x=1)
    with pytest.raises(SystemExit):
        assert tyro.cli(A, args=["--x", "3"])
    assert tyro.cli(A, args=[]) == A(x=None)


def test_multitype_literal() -> None:
    def main(x: Literal[0, "5"]) -> Any:
        return x

    assert tyro.cli(main, args=["--x", "0"]) == 0
    assert tyro.cli(main, args=["--x", "5"]) == "5"
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--x", "6"])


def test_annotated() -> None:
    """Annotated[] is a no-op."""

    @dataclasses.dataclass
    class A:
        x: Annotated[int, "some label"] = 3

    assert tyro.cli(A, args=["--x", "5"]) == A(x=5)


def test_annotated_optional() -> None:
    """Annotated[] is a no-op."""

    @dataclasses.dataclass
    class A:
        x: Annotated[Optional[int], "some label"] = 3

    assert tyro.cli(A, args=[]) == A(x=3)
    assert tyro.cli(A, args=["--x", "5"]) == A(x=5)


def test_optional_annotated() -> None:
    """Annotated[] is a no-op."""

    @dataclasses.dataclass
    class A:
        x: Optional[Annotated[int, "some label"]] = 3

    assert tyro.cli(A, args=[]) == A(x=3)
    assert tyro.cli(A, args=["--x", "5"]) == A(x=5)


def test_final() -> None:
    """Final[] is a no-op."""

    @dataclasses.dataclass
    class A:
        x: Final[int] = 3

    assert tyro.cli(A, args=["--x", "5"]) == A(x=5)


def test_final_optional() -> None:
    @dataclasses.dataclass
    class A:
        x: Final[Optional[int]] = 3

    assert tyro.cli(A, args=[]) == A(x=3)
    assert tyro.cli(A, args=["--x", "5"]) == A(x=5)


def test_classvar() -> None:
    """ClassVar[] types should be skipped."""

    @dataclasses.dataclass
    class A:
        x: ClassVar[int] = 5

    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "1"])
    assert tyro.cli(A, args=[]) == A()


def test_parse_empty_description() -> None:
    """If the file has no dosctring, it should be treated as an empty string."""

    @dataclasses.dataclass
    class A:
        x: int = 0

    assert tyro.cli(A, description=None, args=[]) == A(x=0)


SomeTypeAlias: TypeAlias = int


def test_type_alias() -> None:
    def add(a: SomeTypeAlias, b: SomeTypeAlias) -> SomeTypeAlias:
        return a + b

    assert tyro.cli(add, args=["--a", "5", "--b", "7"]) == 12


def test_any() -> None:
    def main(x: Any = 5) -> Any:
        return x

    assert tyro.cli(main, args=[]) == 5


def test_bytes() -> None:
    def main(x: bytes) -> bytes:
        return x

    assert tyro.cli(main, args=["--x", "hello"]) == b"hello"


def test_any_str() -> None:
    def main(x: AnyStr) -> AnyStr:
        return x

    # Use bytes when provided ascii-compatible inputs.
    assert tyro.cli(main, args=["--x", "hello"]) == b"hello"
    assert tyro.cli(main, args=["--x", "hello„"]) == "hello„"


def test_text() -> None:
    # `Text` is an alias for `str` in Python 3.
    def main(x: Text) -> Text:
        return x

    assert tyro.cli(main, args=["--x", "hello"]) == "hello"
    assert tyro.cli(main, args=["--x", "hello„"]) == "hello„"


def test_fixed() -> None:
    def main(x: Callable[[int], int] = lambda x: x * 2) -> Callable[[int], int]:
        return x

    assert tyro.cli(main, args=[])(3) == 6
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--x", "something"])


def test_fixed_dataclass_type() -> None:
    def dummy():
        return 5  # noqa

    def main(x: Callable = dummy) -> Callable:
        return x

    assert tyro.cli(main, args=[]) is dummy
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--x", "something"])


def test_callable_ellipsis() -> None:
    @dataclasses.dataclass
    class SimpleCallable:
        x: Callable[..., None] = lambda: None

    assert tyro.cli(SimpleCallable, args=[]) == SimpleCallable()


def test_missing_singleton() -> None:
    assert tyro.MISSING is copy.deepcopy(tyro.MISSING)


def test_just_int() -> None:
    assert tyro.cli(int, args=["123"]) == 123


def test_just_dict() -> None:
    assert tyro.cli(Dict[str, str], args="key value key2 value2".split(" ")) == {
        "key": "value",
        "key2": "value2",
    }


def test_just_list() -> None:
    assert tyro.cli(List[int], args="1 2 3 4".split(" ")) == [1, 2, 3, 4]


def test_just_tuple() -> None:
    # Need a type: ignore for mypy. Seems like a mypy bug.
    assert tyro.cli(Tuple[int, int, int, int], args="1 2 3 4".split(" ")) == (  # type: ignore
        1,
        2,
        3,
        4,
    )


def test_return_parser() -> None:
    def main() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser()
        return parser

    assert isinstance(tyro.cli(main, args=[]), argparse.ArgumentParser)


def test_pathlike_custom_class() -> None:
    class CustomPath(pathlib.PurePosixPath):
        def __new__(cls, *args: Union[str, os.PathLike]):
            return super().__new__(cls, *args)

    def main(a: CustomPath) -> CustomPath:
        return a

    assert tyro.cli(main, args=["--a", "/dev/null"]) == CustomPath("/dev/null")


def test_class_with_new_and_no_init() -> None:
    class A(object):
        def __new__(cls, x: int = 5):
            return cls._custom_initializer(x)

        @classmethod
        def _custom_initializer(cls, x: int = 5):
            self = object.__new__(cls)
            self.x = x  # type: ignore
            return self

        def __eq__(self, other) -> bool:
            return self.x == other.x  # type: ignore

    assert tyro.cli(A, args=["--x", "5"]) == A(x=5)


def test_return_unknown_args() -> None:
    @dataclasses.dataclass
    class A:
        x: int = 0

    a, unknown_args = tyro.cli(
        A, args=["positional", "--x", "5", "--y", "7"], return_unknown_args=True
    )
    assert a == A(x=5)
    assert unknown_args == ["positional", "--y", "7"]


def test_unknown_args_with_arg_fixing() -> None:
    @dataclasses.dataclass
    class A:
        x: int = 0

    a, unknown_args = tyro.cli(
        A,
        args=["--x", "5", "--a_b", "--a-c"],
        return_unknown_args=True,
    )
    assert a == A(x=5)
    # Should return the unfixed arguments
    assert unknown_args == ["--a_b", "--a-c"]


def test_allow_ambiguous_args_when_not_returning_unknown_args() -> None:
    @dataclasses.dataclass
    class A:
        a_b: List[int] = dataclasses.field(default_factory=list)

    a = tyro.cli(
        A,
        args=["--a_b", "5", "--a-b", "7"],
    )
    assert a == A(a_b=[7])


def test_disallow_ambiguous_args_when_returning_unknown_args() -> None:
    @dataclasses.dataclass
    class A:
        x: int = 0

    # If there's an argument that's ambiguous then we should raise an error when we're
    # returning unknown args.
    with pytest.raises(RuntimeError, match="Ambiguous .* --a_b and --a-b"):
        tyro.cli(
            A,
            args=["--x", "5", "--a_b", "--a-b"],
            return_unknown_args=True,
        )


def test_unknown_args_with_consistent_duplicates() -> None:
    @dataclasses.dataclass
    class A:
        a_b: List[int] = dataclasses.field(default_factory=list)
        c_d: List[int] = dataclasses.field(default_factory=list)

    # Tests logic for consistent duplicate arguments when performing argument fixing.
    # i.e., we can fix arguments if the separator is consistent (all _'s or all -'s).
    a, unknown_args = tyro.cli(
        A,
        args=[
            "--a-b",
            "5",
            "--a-b",
            "7",
            "--c_d",
            "5",
            "--c_d",
            "7",
            "--e-f",
            "--e-f",
            "--g_h",
            "--g_h",
        ],
        return_unknown_args=True,
    )
    assert a == A(a_b=[7], c_d=[7])
    assert unknown_args == ["--e-f", "--e-f", "--g_h", "--g_h"]


def test_pathlike():
    def main(x: os.PathLike) -> os.PathLike:
        return x

    assert tyro.cli(main, args=["--x", "/dev/null"]) == pathlib.Path("/dev/null")


def test_unpack() -> None:
    def main(*args: int, **kwargs: float) -> Tuple[Tuple[int, ...], Dict[str, float]]:
        return args, kwargs

    assert tyro.cli(main, args=[]) == ((), {})
    assert tyro.cli(main, args="--args --kwargs".split(" ")) == ((), {})
    assert tyro.cli(
        main, args="--args 1 2 3 --kwargs learning_rate 1e-4 beta1 0.99".split(" ")
    ) == ((1, 2, 3), {"learning_rate": 1e-4, "beta1": 0.99})


def test_unpack_with_other_args() -> None:
    def main(
        other1: str, other2: str = "3", *args: int, **kwargs: float
    ) -> Tuple[str, str, Tuple[int, ...], Dict[str, float]]:
        return other1, other2, args, kwargs

    assert tyro.cli(main, args=["--other1", "hi"]) == ("hi", "3", (), {})
    assert tyro.cli(main, args="--other1 ok --args --kwargs".split(" ")) == (
        "ok",
        "3",
        (),
        {},
    )
    assert tyro.cli(
        main,
        args="--args 1 2 3 --kwargs learning_rate 1e-4 beta1 0.99 --other1 hello".split(
            " "
        ),
    ) == ("hello", "3", (1, 2, 3), {"learning_rate": 1e-4, "beta1": 0.99})


def test_empty_container() -> None:
    @dataclasses.dataclass
    class A:
        x: Tuple[int, ...] = (1, 2, 3)
        y: Union[int, str, List[bool]] = dataclasses.field(
            default_factory=lambda: [False, False, True]
        )

    assert tyro.cli(A, args="--x".split(" ")).x == ()
    assert tyro.cli(A, args="--y".split(" ")).y == []


def test_unknown_args_with_consistent_duplicates_use_underscores() -> None:
    @dataclasses.dataclass
    class A:
        a_b: List[int] = dataclasses.field(default_factory=list)
        c_d: List[int] = dataclasses.field(default_factory=list)

    # Tests logic for consistent duplicate arguments when performing argument fixing.
    # i.e., we can fix arguments if the separator is consistent (all _'s or all -'s).
    a, unknown_args = tyro.cli(
        A,
        args=[
            "--a-b",
            "5",
            "--a-b",
            "7",
            "--c_d",
            "5",
            "--c_d",
            "7",
            "--e-f",
            "--e-f",
            "--g_h",
            "--g_h",
        ],
        return_unknown_args=True,
        use_underscores=True,
    )
    assert a == A(a_b=[7], c_d=[7])
    assert unknown_args == ["--e-f", "--e-f", "--g_h", "--g_h"]


def test_datetime_parsing() -> None:
    assert tyro.cli(
        datetime.datetime, args=["2024-08-25T14:30:00"]
    ) == datetime.datetime(2024, 8, 25, 14, 30, 0)
    assert tyro.cli(
        datetime.datetime, args=["2024-08-25T14:30:00.123456"]
    ) == datetime.datetime(2024, 8, 25, 14, 30, 0, 123456)
    assert tyro.cli(
        datetime.datetime, args=["2024-08-25T14:30:00+05:30"]
    ) == datetime.datetime(
        2024, 8, 25, 14, 30, tzinfo=datetime.timezone(datetime.timedelta(seconds=19800))
    )


def test_date_parsing() -> None:
    assert tyro.cli(datetime.date, args=["2024-08-25"]) == datetime.date(2024, 8, 25)
    assert tyro.cli(datetime.date, args=["1999-12-31"]) == datetime.date(1999, 12, 31)


def test_time_parsing() -> None:
    assert tyro.cli(datetime.time, args=["14:30:00"]) == datetime.time(14, 30, 0)
    assert tyro.cli(datetime.time, args=["14:30:00.123456"]) == datetime.time(
        14, 30, 0, 123456
    )
    assert tyro.cli(datetime.time, args=["14:30:00+05:30"]) == datetime.time(
        14, 30, tzinfo=datetime.timezone(datetime.timedelta(seconds=19800))
    )


def test_datetime_parsing_with_main():
    def main(dt: datetime.datetime) -> datetime.datetime:
        return dt

    assert tyro.cli(main, args=["--dt", "2024-08-25T14:30:00"]) == datetime.datetime(
        2024, 8, 25, 14, 30, 0
    )
    assert tyro.cli(
        main, args=["--dt", "2024-08-25T14:30:00.123456"]
    ) == datetime.datetime(2024, 8, 25, 14, 30, 0, 123456)
    assert tyro.cli(
        main, args=["--dt", "2024-08-25T14:30:00+05:30"]
    ) == datetime.datetime(
        2024, 8, 25, 14, 30, tzinfo=datetime.timezone(datetime.timedelta(seconds=19800))
    )


def test_date_parsing_with_main():
    def main(dt: datetime.date) -> datetime.date:
        return dt

    assert tyro.cli(main, args=["--dt", "2024-08-25"]) == datetime.date(2024, 8, 25)
    assert tyro.cli(main, args=["--dt", "1999-12-31"]) == datetime.date(1999, 12, 31)


def test_time_parsing_with_main():
    def main(dt: datetime.time) -> datetime.time:
        return dt

    assert tyro.cli(main, args=["--dt", "14:30:00"]) == datetime.time(14, 30, 0)
    assert tyro.cli(main, args=["--dt", "14:30:00.123456"]) == datetime.time(
        14, 30, 0, 123456
    )
    assert tyro.cli(main, args=["--dt", "14:30:00+05:30"]) == datetime.time(
        14, 30, tzinfo=datetime.timezone(datetime.timedelta(seconds=19800))
    )


def test_date_parsing_harder_format():
    def main(dt: datetime.date) -> datetime.date:
        return dt

    # Wrong separator '/'.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--dt", "2024/08/25"])

    # Day-Month-Year format instead of Year-Month-Day.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--dt", "25-08-2024"])


def test_time_parsing_harder_format():
    def main(dt: datetime.time) -> datetime.time:
        return dt

    # Wrong separator '/'.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--dt", "14/30"])

    # Missing seconds.
    assert tyro.cli(main, args=["--dt", "14:30"]) == datetime.time(14, 30, 0)

    # Invalid minute value.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--dt", "14:60:00"])

    # Invalid hour value.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--dt", "25:00:00"])


def test_numeric_tower() -> None:
    @dataclasses.dataclass(frozen=True)
    class NumericTower:
        a: Union[complex, str] = 3.0
        b: Union[bytearray, str] = dataclasses.field(
            default_factory=lambda: bytearray(b"123")
        )
        c: Union[complex, str] = True
        d: Union[int, complex] = False
        e: Union[float, str] = 3

    assert tyro.cli(NumericTower, args=[]) == NumericTower(3.0)
    assert tyro.cli(NumericTower, args="--a 1+3j".split(" ")) == NumericTower(1 + 3j)
    assert tyro.cli(NumericTower, args="--c False".split(" ")) == NumericTower(
        c="False"
    )
    assert tyro.cli(NumericTower, args="--e 3.2".split(" ")) == NumericTower(e=3.2)
    with pytest.raises(SystemExit):
        tyro.cli(NumericTower, args="--d False".split(" "))


def test_runtime_checkable_edge_case() -> None:
    """From Kevin Black: https://github.com/brentyi/tyro/issues/214"""

    @runtime_checkable
    class DummyProtocol(Protocol):
        pass

    @dataclasses.dataclass(frozen=True)
    class SubConfigA:
        pass

    @dataclasses.dataclass(frozen=True)
    class SubConfigB:
        pass

    @dataclasses.dataclass
    class Config:
        subconfig: DummyProtocol

    CONFIGS = {
        "a": Config(subconfig=SubConfigA()),
        "b": Config(subconfig=SubConfigB()),
    }

    assert (
        tyro.extras.overridable_config_cli(
            {k: (k, v) for k, v in CONFIGS.items()}, args=["a"]
        ).subconfig
        == SubConfigA()
    )
    assert (
        tyro.extras.overridable_config_cli(
            {k: (k, v) for k, v in CONFIGS.items()}, args=["b"]
        ).subconfig
        == SubConfigB()
    )


def test_linear_inheritance() -> None:
    @dataclasses.dataclass(frozen=True)
    class A:
        field: Union[str, int] = 5

    @dataclasses.dataclass(frozen=True)
    class B(A):
        field: int = 10

    @dataclasses.dataclass(frozen=True)
    class C(B):
        pass

    helptext = get_helptext_with_checks(C)
    assert "5" not in helptext
    assert "10" in helptext
    assert "INT" in helptext
    assert tyro.cli(C, args=[]) == C(10)
    assert tyro.cli(C, args=["--field", "3"]) == C(3)
    assert tyro.cli(A, args=["--field", "3"]) == A("3")


def test_diamond_inheritance() -> None:
    @dataclasses.dataclass(frozen=True)
    class A:
        field: Union[int, str] = 5

    @dataclasses.dataclass(frozen=True)
    class B(A):
        pass

    @dataclasses.dataclass(frozen=True)
    class C(A):
        field: int = 10

    @dataclasses.dataclass(frozen=True)
    class D(B, C):
        pass

    helptext = get_helptext_with_checks(D)
    # Despite C coming earlier in the MRO than A, the field is inherited from
    # A. This appears to be a Python bug.
    # https://github.com/python/cpython/issues/108611
    assert "5" in helptext
    assert "10" not in helptext

    # The type, however, currently comes from C. This matches the MRO and the
    # behavior of pyright and mypy but not of dataclasses.fields().
    assert "INT|STR" not in helptext


def test_partial_annotation() -> None:
    class A:
        def __init__(self, b=[], c: float = 1):
            super(A, self).__init__()
            del b
            del c

    def main(opt: A = A()):
        del opt

    assert "--opt.b" in get_helptext_with_checks(main)
    assert "{fixed}" in get_helptext_with_checks(main)
    assert "--opt.c" in get_helptext_with_checks(main)
