# mypy: disable-error-code="call-overload,misc"
#
# Mypy errors from passing union types directly into tyro.cli() as Type[T]. We would
# benefit from TypeForm[T]: https://github.com/python/mypy/issues/9773
import collections
import collections.abc
import contextlib
import dataclasses
import enum
import io
import sys
from typing import (
    Any,
    Deque,
    Dict,
    FrozenSet,
    List,
    Literal,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
)

import pytest
from helptext_utils import get_helptext_with_checks

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
    with pytest.raises(SystemExit), contextlib.redirect_stderr(target):
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


def test_sequences_narrow() -> None:
    @dataclasses.dataclass
    class A:
        x: Sequence = dataclasses.field(default_factory=lambda: [0])

    assert tyro.cli(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
    assert tyro.cli(A, args=[]) == A(x=[0])
    assert tyro.cli(A, args=["--x"]) == A(x=[])


def test_sequences_narrow_any() -> None:
    @dataclasses.dataclass
    class A:
        x: Sequence[Any] = dataclasses.field(default_factory=lambda: [0])

    assert tyro.cli(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
    assert tyro.cli(A, args=[]) == A(x=[0])
    assert tyro.cli(A, args=["--x"]) == A(x=[])


if sys.version_info >= (3, 9):

    def test_abc_sequences() -> None:
        @dataclasses.dataclass
        class A:
            x: collections.abc.Sequence[int]

        assert tyro.cli(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
        assert tyro.cli(A, args=["--x"]) == A(x=[])
        with pytest.raises(SystemExit):
            tyro.cli(A, args=[])


def test_abc_sequences_narrow() -> None:
    @dataclasses.dataclass
    class A:
        x: collections.abc.Sequence = dataclasses.field(default_factory=lambda: [0])

    assert tyro.cli(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
    assert tyro.cli(A, args=[]) == A(x=[0])
    assert tyro.cli(A, args=["--x"]) == A(x=[])


if sys.version_info >= (3, 9):

    def test_abc_sequences_narrow_any() -> None:
        @dataclasses.dataclass
        class A:
            x: collections.abc.Sequence[Any] = dataclasses.field(
                default_factory=lambda: [0]
            )

        assert tyro.cli(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
        assert tyro.cli(A, args=[]) == A(x=[0])
        assert tyro.cli(A, args=["--x"]) == A(x=[])


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
    def main(a: Tuple[float, ...] | Tuple[int, ...]) -> Any:
        return a

    assert tyro.cli(main, args="--a 3.3 3.3 7.0".split(" ")) == (3.3, 3.3, 7.0)
    assert tyro.cli(main, args="--a 3 3 7".split(" ")) == (3, 3, 7)


def test_union_over_collections_2() -> None:
    def main(a: Tuple[str, float, str] | Tuple[str, str, float]) -> Any:
        return a

    assert tyro.cli(main, args="--a 3.3 hey 7.0".split(" ")) == ("3.3", "hey", 7.0)
    assert tyro.cli(main, args="--a 3 3 hey".split(" ")) == ("3", 3.0, "hey")


def test_union_over_collections_3() -> None:
    def main(a: Tuple[int, int] | Tuple[int, int, int]) -> Tuple[int, ...]:
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
                    Tuple[int, int] | Tuple[str, str],
                ]
            ]
        ] = None,
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


def test_dict_no_annotation_2() -> None:
    def main(x: Dict = {"int": 5, "str": "5"}):
        return x

    assert tyro.cli(main, args=[]) == {"int": 5, "str": "5"}
    assert tyro.cli(main, args="--x.int 3 --x.str 7".split(" ")) == {
        "int": 3,
        "str": "7",
    }


def test_dict_optional() -> None:
    # In this case, the `None` is ignored.
    def main(x: Optional[Dict[str, float]] = {"three": 3, "five": 5}):
        return x

    assert tyro.cli(main, args=[]) == {"three": 3, "five": 5}
    assert tyro.cli(main, args="--x 3 3 5 5".split(" ")) == {"3": 3, "5": 5}


def test_double_dict_no_annotation() -> None:
    def main(
        x: Dict[str, Any] = {
            "wow": {"int": 5, "str": "5"},
        },
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


def test_list_narrowing_any() -> None:
    def main(x: List[Any] = [0, 1, 2, "hello"]) -> Any:
        return x

    assert tyro.cli(main, args="--x hi there 5".split(" ")) == ["hi", "there", 5]


def test_list_narrowing_empty() -> None:
    def main(x: list = []) -> Any:
        return x

    assert tyro.cli(main, args="--x hi there 5".split(" ")) == ["hi", "there", "5"]


def test_list_narrowing_empty_any() -> None:
    def main(x: List[Any] = []) -> Any:
        return x

    assert tyro.cli(main, args="--x hi there 5".split(" ")) == ["hi", "there", "5"]


def test_set_narrowing() -> None:
    def main(x: set = {0, 1, 2, "hello"}) -> Any:
        return x

    out = tyro.cli(main, args="--x hi there 5".split(" "))
    # Nondeterministic depending on set iteration order, `int | str` or `str | int`.
    assert out in ({"hi", "there", 5}, {"hi", "there", "5"})


def test_set_narrowing_any() -> None:
    def main(x: Set[Any] = {0, 1, 2, "hello"}) -> Any:
        return x

    out = tyro.cli(main, args="--x hi there 5".split(" "))
    # Nondeterministic depending on set iteration order, `int | str` or `str | int`.
    assert out in ({"hi", "there", 5}, {"hi", "there", "5"})


def test_set_narrowing_empty() -> None:
    def main(x: set = set()) -> Any:
        return x

    assert tyro.cli(main, args="--x hi there 5".split(" ")) == {"hi", "there", "5"}


def test_set_narrowing_any_empty() -> None:
    def main(x: Set[Any] = set()) -> Any:
        return x

    assert tyro.cli(main, args="--x hi there 5".split(" ")) == {"hi", "there", "5"}


def test_tuple_narrowing() -> None:
    def main(x: tuple = (0, 1, 2, "hello")) -> Any:
        return x

    assert tyro.cli(main, args="--x 0 1 2 3".split(" ")) == (0, 1, 2, "3")


def test_tuple_narrowing_any() -> None:
    def main(x: Tuple[Any, ...] = (0, 1, 2, "hello")) -> Any:
        return x

    assert tyro.cli(main, args="--x 0 1 2 3".split(" ")) == (0, 1, 2, "3")


def test_tuple_narrowing_empty() -> None:
    def main(x: tuple = ()) -> Any:
        return x

    assert tyro.cli(main, args="--x 0 1 2 3".split(" ")) == ("0", "1", "2", "3")


def test_tuple_narrowing_empty_any() -> None:
    def main(x: Tuple[Any, ...] = ()) -> Any:
        return x

    assert tyro.cli(main, args="--x 0 1 2 3".split(" ")) == ("0", "1", "2", "3")


def test_tuple_narrowing_empty_default() -> None:
    def main(x: tuple = ()) -> Any:
        return x

    assert tyro.cli(main, args="--x 0 1 2 3".split(" ")) == ("0", "1", "2", "3")


def test_narrowing_edge_case() -> None:
    """https://github.com/brentyi/tyro/issues/136"""

    @dataclasses.dataclass
    class Config:
        _target: Type = dataclasses.field(default_factory=lambda: MyClass)

    class MyClass:
        def __len__(self):
            return 0

    assert tyro.cli(Config, args=[]) == Config()


def test_no_type_collections():
    assert tyro.cli(dict, args="a b c d".split(" ")) == {"a": "b", "c": "d"}
    assert tyro.cli(list, args="a b c d".split(" ")) == ["a", "b", "c", "d"]
    assert tyro.cli(tuple, args="a b c d".split(" ")) == ("a", "b", "c", "d")
    assert tyro.cli(set, args="a b c d".split(" ")) == {"a", "b", "c", "d"}


def test_list_narrowing_alt() -> None:
    def main(x: list = [1, "1"]) -> list:
        return x

    assert tyro.cli(main, args="--x 3 four 5".split(" ")) == [3, "four", 5]


def test_list_narrowing_direct() -> None:
    assert tyro.cli(list, default=[1, "2"], args="3 four 5".split(" ")) == [
        3,
        "four",
        5,
    ]


def test_tuple_direct() -> None:
    assert tyro.cli(Tuple[int, ...], args="1 2".split(" ")) == (1, 2)  # type: ignore
    assert tyro.cli(Tuple[int, int], args="1 2".split(" ")) == (1, 2)  # type: ignore


def test_nested_dict_in_list() -> None:
    """https://github.com/nerfstudio-project/nerfstudio/pull/3567"""

    @dataclasses.dataclass
    class Args:
        proposal_net_args_list: List[Dict] = dataclasses.field(
            default_factory=lambda: [
                {
                    "hidden_dim": 16,
                },
                {
                    "hidden_dim": 16,
                },
            ]
        )
        proposal_net_args_list2: Tuple[Dict[str, List], Dict[str, List]] = (
            dataclasses.field(
                default_factory=lambda: (
                    {
                        "hidden_dim": [16, 32],
                    },
                    {
                        "hidden_dim": [16, 32],
                    },
                )
            )
        )

    assert tyro.cli(Args, args=[]) == Args()
    assert tyro.cli(
        Args, args=["--proposal-net-args-list.0.hidden-dim", "32"]
    ).proposal_net_args_list == (
        [
            {
                "hidden_dim": 32,
            },
            {
                "hidden_dim": 16,
            },
        ]
    )
    assert tyro.cli(
        Args, args=["--proposal-net-args-list2.1.hidden-dim", "32", "64"]
    ).proposal_net_args_list2 == (
        {
            "hidden_dim": [16, 32],
        },
        {
            "hidden_dim": [32, 64],
        },
    )


def test_double_list_in_tuple() -> None:
    def main(x: Tuple[List[str], List[str]]) -> None:
        del x

    # This used to be ambiguous, we now break it into two separate arguments!
    helptext = get_helptext_with_checks(main)
    assert "--x.0 [STR [STR ...]]" in helptext
    assert "--x.1 [STR [STR ...]]" in helptext


def test_ambiguous_collection_0() -> None:
    @dataclasses.dataclass
    class A:
        x: Tuple[Tuple[int, ...], ...]

    assert tyro.cli(A, args=["--x", "0", "1"]) == A(x=((0, 1),))


def test_ambiguous_collection_1() -> None:
    @dataclasses.dataclass
    class A:
        x: List[List[int]]

    assert tyro.cli(A, args=["--x", "0", "1"]).x == [[0, 1]]


def test_ambiguous_collection_2() -> None:
    assert tyro.cli(Tuple[List[str], ...], args=["a", "b", "c", "d"]) == (
        ["a", "b", "c", "d"],
    )


def test_ambiguous_collection_3() -> None:
    assert tyro.cli(Dict[Tuple[int, ...], str], args=["0", "1", "a"]) == {(0, 1): "a"}


def test_ambiguous_collection_4() -> None:
    @dataclasses.dataclass
    class A:
        x: Dict[str, List[int]]

    assert tyro.cli(A, args=["--x", "a", "0", "1"]).x == {"a": [0, 1]}


def test_ambiguous_collection_5() -> None:
    @dataclasses.dataclass
    class A:
        x: Dict[Tuple[int, ...], str]

    assert tyro.cli(A, args=["--x", "0", "1", "a"]).x == {(0, 1): "a"}


def test_ambiguous_collection_6() -> None:
    @dataclasses.dataclass
    class A:
        x: Dict[Tuple[Tuple[Tuple[int, ...]]], str]

    assert tyro.cli(A, args=["--x", "0", "1", "a", "2", "3"]).x == {
        (((0, 1),),): "a",
        (((2,),),): "3",
    }


def test_ambiguous_collection_7() -> None:
    @dataclasses.dataclass
    class A:
        x: Tuple[List[str], int, List[str]]

    # We resolve ambiguity in fixed-length tuples by breaking inputs into
    # separate arguments.
    assert tyro.cli(
        A, args=["--x.0", "0", "1", "a", "2", "3", "--x.1", "0", "--x.2", "4"]
    ).x == (
        ["0", "1", "a", "2", "3"],
        0,
        ["4"],
    )
