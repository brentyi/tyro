import collections
import contextlib
import dataclasses
import enum
import io
from typing import (
    Any,
    Deque,
    Dict,
    FrozenSet,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

import pytest
from typing_extensions import Literal

import tyro


def test_tuples_fixed() -> None:
    @dataclasses.dataclass
    class A:
        x: Tuple[int, int, int]

    assert tyro.cli(A, args=["--x", "1", "2", "3"]) == A(x=(1, 2, 3))
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x"])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])


def test_tuples_fixed_mixed() -> None:
    @dataclasses.dataclass
    class A:
        x: Tuple[int, str, int]

    assert tyro.cli(A, args=["--x", "1", "2", "3"]) == A(x=(1, "2", 3))
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x"])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])


def test_tuples_with_default() -> None:
    @dataclasses.dataclass
    class A:
        x: Tuple[int, int, int] = (0, 1, 2)

    assert tyro.cli(A, args=[]) == A(x=(0, 1, 2))
    assert tyro.cli(A, args=["--x", "1", "2", "3"]) == A(x=(1, 2, 3))
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x"])


def test_tuple_with_literal_and_default() -> None:
    @dataclasses.dataclass
    class A:
        x: Tuple[Literal[1, 2, 3], ...] = (1, 2)

    assert tyro.cli(A, args=["--x", "1", "2", "3"]) == A(x=(1, 2, 3))
    assert tyro.cli(A, args=[]) == A(x=(1, 2))
    assert tyro.cli(A, args=["--x"]) == A(x=())
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "1", "2", "3", "4"])


def test_positional_tuple_with_literal_and_default() -> None:
    @dataclasses.dataclass
    class A:
        x: tyro.conf.Positional[Tuple[Literal[1, 2, 3], ...]] = (1, 2)

    assert tyro.cli(A, args=["1", "2", "3"]) == A(x=(1, 2, 3))
    assert tyro.cli(A, args=[]) == A(x=(1, 2))

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(A, args=["1", "2", "3", "4"])
    assert "invalid choice" in target.getvalue()


def test_tuples_fixed_multitype() -> None:
    @dataclasses.dataclass
    class A:
        x: Tuple[int, str, float]

    assert tyro.cli(A, args=["--x", "1", "2", "3.5"]) == A(x=(1, "2", 3.5))
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x"])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])


def test_tuples_fixed_bool() -> None:
    @dataclasses.dataclass
    class A:
        x: Tuple[bool, bool, bool]

    assert tyro.cli(A, args=["--x", "True", "True", "False"]) == A(
        x=(True, True, False)
    )
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x"])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])


def test_tuples_variable() -> None:
    @dataclasses.dataclass
    class A:
        x: Tuple[int, ...]

    assert tyro.cli(A, args=["--x", "1", "2", "3"]) == A(x=(1, 2, 3))
    assert tyro.cli(A, args=["--x"]) == A(x=())
    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])


def test_tuples_variable_bool() -> None:
    @dataclasses.dataclass
    class A:
        x: Tuple[bool, ...]

    assert tyro.cli(A, args=["--x", "True", "True", "False"]) == A(
        x=(True, True, False)
    )
    assert tyro.cli(A, args=["--x"]) == A(x=())
    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])


def test_tuples_variable_optional() -> None:
    @dataclasses.dataclass
    class A:
        x: Optional[Tuple[int, ...]] = None

    assert tyro.cli(A, args=["--x", "1", "2", "3"]) == A(x=(1, 2, 3))
    assert tyro.cli(A, args=["--x"]) == A(x=())
    assert tyro.cli(A, args=[]) == A(x=None)


def test_sequences() -> None:
    @dataclasses.dataclass
    class A:
        x: Sequence[int]

    assert tyro.cli(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
    assert tyro.cli(A, args=["--x"]) == A(x=[])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])


def test_lists() -> None:
    @dataclasses.dataclass
    class A:
        x: List[int]

    assert tyro.cli(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
    assert tyro.cli(A, args=["--x"]) == A(x=[])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])


def test_list_with_literal() -> None:
    @dataclasses.dataclass
    class A:
        x: List[Literal[1, 2, 3]]

    assert tyro.cli(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
    assert tyro.cli(A, args=["--x"]) == A(x=[])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "1", "2", "3", "4"])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])


def test_list_with_enums() -> None:
    class Color(enum.Enum):
        RED = enum.auto()
        GREEN = enum.auto()
        BLUE = enum.auto()

    @dataclasses.dataclass
    class A:
        x: List[Color]

    assert tyro.cli(A, args=["--x", "RED", "RED", "BLUE"]) == A(
        x=[Color.RED, Color.RED, Color.BLUE]
    )
    assert tyro.cli(A, args=["--x"]) == A(x=[])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "RED", "RED", "YELLOW"])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])


def test_lists_with_default() -> None:
    class Color(enum.Enum):
        RED = enum.auto()
        GREEN = enum.auto()
        BLUE = enum.auto()

    @dataclasses.dataclass
    class A:
        x: List[Color] = dataclasses.field(
            default_factory=[Color.RED, Color.GREEN].copy
        )

    assert tyro.cli(A, args=[]) == A(x=[Color.RED, Color.GREEN])
    assert tyro.cli(A, args=["--x", "RED", "GREEN", "BLUE"]) == A(
        x=[Color.RED, Color.GREEN, Color.BLUE]
    )


def test_lists_bool() -> None:
    @dataclasses.dataclass
    class A:
        x: List[bool]

    assert tyro.cli(A, args=["--x", "True", "False", "True"]) == A(
        x=[True, False, True]
    )
    assert tyro.cli(A, args=["--x"]) == A(x=[])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])


def test_sets() -> None:
    @dataclasses.dataclass
    class A:
        x: Set[int]

    assert tyro.cli(A, args=["--x", "1", "2", "3", "3"]) == A(x={1, 2, 3})
    assert tyro.cli(A, args=["--x"]) == A(set())
    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])


def test_frozen_sets() -> None:
    @dataclasses.dataclass
    class A:
        x: FrozenSet[int]

    assert tyro.cli(A, args=["--x", "1", "2", "3", "3"]) == A(x=frozenset({1, 2, 3}))
    assert tyro.cli(A, args=["--x"]) == A(x=frozenset())
    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])


def test_deque() -> None:
    @dataclasses.dataclass
    class A:
        x: Deque[int]

    assert tyro.cli(A, args=["--x", "1", "2", "3", "3"]) == A(
        x=collections.deque([1, 2, 3, 3])
    )
    assert tyro.cli(A, args=["--x"]) == A(collections.deque())
    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])


def test_sets_with_default() -> None:
    @dataclasses.dataclass
    class A:
        x: Set[int] = dataclasses.field(default_factory={0, 1, 2}.copy)

    assert tyro.cli(A, args=[]) == A(x={0, 1, 2})
    assert tyro.cli(A, args=["--x", "1", "2", "3", "3"]) == A(x={1, 2, 3})
    assert tyro.cli(A, args=["--x"]) == A(x=set())


def test_optional_sequences() -> None:
    @dataclasses.dataclass
    class A:
        x: Optional[Sequence[int]] = None

    assert tyro.cli(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
    assert tyro.cli(A, args=["--x"]) == A(x=[])
    assert tyro.cli(A, args=["--x", "None"]) == A(x=None)
    assert tyro.cli(A, args=[]) == A(x=None)


def test_optional_lists() -> None:
    @dataclasses.dataclass
    class A:
        x: Optional[List[int]] = None

    assert tyro.cli(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
    assert tyro.cli(A, args=["--x"]) == A(x=[])
    assert tyro.cli(A, args=["--x", "None"]) == A(x=None)
    assert tyro.cli(A, args=[]) == A(x=None)


def test_nested_optional_types() -> None:
    """We support "None" as a special-case keyword. (note: this is a bit weird because
    Optional[str] might interpret "None" as either a string or an actual `None`
    value)"""

    @dataclasses.dataclass
    class A:
        x: Tuple[Optional[int], ...]

    assert tyro.cli(A, args=["--x", "0", "1"]) == A((0, 1))
    assert tyro.cli(A, args=["--x", "0", "None", "1"]) == A((0, None, 1))


def test_union_over_collections() -> None:
    def main(a: Union[Tuple[float, ...], Tuple[int, ...]]) -> Any:
        return a

    assert tyro.cli(main, args="--a 3.3 3.3 7.0".split(" ")) == (3.3, 3.3, 7.0)
    assert tyro.cli(main, args="--a 3 3 7".split(" ")) == (3, 3, 7)


def test_union_over_collections_2() -> None:
    def main(a: Union[Tuple[str, float, str], Tuple[str, str, float]]) -> Any:
        return a

    assert tyro.cli(main, args="--a 3.3 hey 7.0".split(" ")) == ("3.3", "hey", 7.0)
    assert tyro.cli(main, args="--a 3 3 hey".split(" ")) == ("3", 3.0, "hey")


def test_union_over_collections_3() -> None:
    def main(a: Union[Tuple[int, int], Tuple[int, int, int]]) -> Tuple[int, ...]:
        return a

    assert tyro.cli(main, args=["--a", "5", "5"]) == (5, 5)
    assert tyro.cli(main, args=["--a", "1", "2", "3"]) == (1, 2, 3)

    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--a", "5", "5", "2", "1"])

    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--a"])
    with pytest.raises(SystemExit):
        tyro.cli(main, args=[])


def test_choices_in_tuples_0() -> None:
    @dataclasses.dataclass
    class A:
        x: Tuple[bool, bool]

    assert tyro.cli(A, args=["--x", "True", "False"]) == A((True, False))


def test_choices_in_tuples_1() -> None:
    @dataclasses.dataclass
    class A:
        x: Tuple[bool, Literal["True", "False"]]

    assert tyro.cli(A, args=["--x", "True", "False"]) == A((True, "False"))


def test_choices_in_tuples_2() -> None:
    @dataclasses.dataclass
    class A:
        x: Tuple[bool, Literal["True", "False", "None"]]

    assert tyro.cli(A, args=["--x", "True", "False"]).x == (True, "False")
    assert tyro.cli(A, args=["--x", "False", "None"]).x == (False, "None")
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "None", "False"])


def test_nested_tuple_types() -> None:
    @dataclasses.dataclass
    class A:
        x: Tuple[Tuple[int, int], Tuple[str, str]]

    assert tyro.cli(A, args="--x 5 5 5 5".split(" ")).x == ((5, 5), ("5", "5"))


def test_variable_nested_tuple() -> None:
    def main(x: Tuple[Tuple[int, str], ...]) -> tuple:
        return x

    assert tyro.cli(main, args="--x 1 1 2 2".split(" ")) == ((1, "1"), (2, "2"))
    with pytest.raises(SystemExit):
        tyro.cli(main, args="--x 1 1 2".split(" "))


def test_super_nested() -> None:
    def main(
        x: Optional[
            List[
                Tuple[
                    Optional[int],
                    Literal[3, 4],
                    Union[Tuple[int, int], Tuple[str, str]],
                ]
            ]
        ] = None
    ) -> Any:
        return x

    assert tyro.cli(main, args=[]) is None
    assert tyro.cli(main, args="--x None".split(" ")) is None
    assert tyro.cli(main, args="--x None 3 2 2".split(" ")) == [(None, 3, (2, 2))]
    assert tyro.cli(main, args="--x 2 3 x 2".split(" ")) == [(2, 3, ("x", "2"))]
    assert tyro.cli(main, args="--x 2 3 x 2 2 3 1 2".split(" ")) == [
        (2, 3, ("x", "2")),
        (2, 3, (1, 2)),
    ]
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--help"])


def test_dict_no_annotation() -> None:
    def main(x: Dict[str, Any] = {"int": 5, "str": "5"}):
        return x

    assert tyro.cli(main, args=[]) == {"int": 5, "str": "5"}
    assert tyro.cli(main, args="--x.int 3 --x.str 7".split(" ")) == {
        "int": 3,
        "str": "7",
    }


def test_double_dict_no_annotation() -> None:
    def main(
        x: Dict[str, Any] = {
            "wow": {"int": 5, "str": "5"},
        }
    ):
        return x

    assert tyro.cli(main, args=[]) == {"wow": {"int": 5, "str": "5"}}
    assert tyro.cli(main, args="--x.wow.int 3 --x.wow.str 7".split(" ")) == {
        "wow": {
            "int": 3,
            "str": "7",
        }
    }


def test_list_narrowing() -> None:
    def main(x: list = [0, 1, 2, "hello"]) -> Any:
        return x

    assert tyro.cli(main, args="--x hi there 5".split(" ")) == ["hi", "there", 5]


def test_set_narrowing() -> None:
    def main(x: set = {0, 1, 2, "hello"}) -> Any:
        return x

    assert tyro.cli(main, args="--x hi there 5".split(" ")) == {"hi", "there", 5}


def test_tuple_narrowing() -> None:
    def main(x: tuple = (0, 1, 2, "hello")) -> Any:
        return x

    assert tyro.cli(main, args="--x 0 1 2 3".split(" ")) == (0, 1, 2, "3")


def test_no_type_collections():
    assert tyro.cli(dict, args="a b c d".split(" ")) == {"a": "b", "c": "d"}
    assert tyro.cli(list, args="a b c d".split(" ")) == ["a", "b", "c", "d"]
    assert tyro.cli(tuple, args="a b c d".split(" ")) == ("a", "b", "c", "d")
    assert tyro.cli(set, args="a b c d".split(" ")) == {"a", "b", "c", "d"}
