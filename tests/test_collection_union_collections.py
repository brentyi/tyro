# mypy: disable-error-code="call-overload,misc"
#
# Mypy errors from passing union types directly into tyro.cli() as Type[T]. We would
# benefit from TypeForm[T]: https://github.com/python/mypy/issues/9773
"""Tests for collections containing unions with different fixed nargs.

This tests the functionality added to support types like:
- List[Union[bool, Tuple[int, int]]]
- List[Union[Tuple[int, int], Tuple[int, int, int]]]
"""

import dataclasses
from typing import Any, List, Tuple, Union

import pytest
from helptext_utils import get_helptext_with_checks

import tyro


def test_list_bool_or_tuple() -> None:
    """Test list containing union of bool and fixed-size tuple."""
    assert tyro.cli(List[Union[bool, Tuple[int, int]]], args="3 4 5 6".split(" ")) == [
        (3, 4),
        (5, 6),
    ]
    assert tyro.cli(
        List[Union[bool, Tuple[int, int]]], args="True 3 4 5 6 False".split(" ")
    ) == [
        True,
        (3, 4),
        (5, 6),
        False,
    ]


def test_list_union_different_tuple_sizes() -> None:
    """Test list containing union of tuples with different sizes."""

    def main(
        x: List[Union[Tuple[int, int], Tuple[int, int, int]]],
    ) -> List[Union[Tuple[int, int], Tuple[int, int, int]]]:
        return x

    # This is now supported! Test that it works correctly.
    assert tyro.cli(main, args=["--x", "1", "2", "3", "4"]) == [(1, 2), (3, 4)]
    assert tyro.cli(main, args=["--x", "1", "2", "3", "4", "5", "6"]) == [
        (1, 2),
        (3, 4),
        (5, 6),
    ]

    # With backtracking, "1 2 3" now works!
    assert tyro.cli(main, args=["--x", "1", "2", "3"]) == [(1, 2, 3)]


def test_list_union_different_tuple_sizes_direct() -> None:
    """Test directly passing the type annotation to tyro.cli."""
    X = List[Union[Tuple[int, int], Tuple[int, int, int]]]
    # This is now supported!
    assert tyro.cli(X, args=["1", "2", "3", "4"]) == [(1, 2), (3, 4)]
    assert tyro.cli(X, args=["1", "2", "3", "4", "5", "6"]) == [(1, 2), (3, 4), (5, 6)]


def test_union_over_collections_from_test_collections() -> None:
    """Test from test_collections.py that now works."""

    def main(a: Union[Tuple[int, int], Tuple[int, int, int]]) -> Tuple[int, ...]:
        return a

    assert tyro.cli(main, args=["--a", "5", "5"]) == (5, 5)
    assert tyro.cli(main, args=["--a", "5", "5", "2"]) == (5, 5, 2)
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--a", "5", "5", "2", "1"])
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--a"])


def test_list_union_with_str_and_tuple() -> None:
    """Test list containing union of string and tuple."""

    def main(x: List[Union[str, Tuple[int, int]]]) -> List[Union[str, Tuple[int, int]]]:
        return x

    # When str is in a union with tuple, str will match because both have fixed nargs
    # and the parsing tries options from left to right.
    assert tyro.cli(main, args=["--x", "hello", "1", "2", "world"]) == [
        "hello",
        "1",
        "2",
        "world",
    ]
    assert tyro.cli(main, args=["--x", "1", "2", "3", "4"]) == ["1", "2", "3", "4"]

    # Even with tuple first, strings that can be parsed as strings will be.
    def main2(
        x: List[Union[Tuple[int, int], str]],
    ) -> List[Union[Tuple[int, int], str]]:
        return x

    # When all args can be parsed as strings, they will be.
    assert tyro.cli(main2, args=["--x", "1", "2", "hello", "3", "4"]) == [
        "1",
        "2",
        "hello",
        "3",
        "4",
    ]


def test_list_union_triple_tuple_sizes() -> None:
    """Test list containing union of three different tuple sizes."""

    def main(
        x: List[Union[Tuple[int], Tuple[int, int], Tuple[int, int, int]]],
    ) -> List[Union[Tuple[int], Tuple[int, int], Tuple[int, int, int]]]:
        return x

    # Should parse greedily, trying single int first.
    assert tyro.cli(main, args=["--x", "1", "2", "3"]) == [(1,), (2,), (3,)]
    assert tyro.cli(main, args=["--x", "1", "2", "3", "4", "5", "6"]) == [
        (1,),
        (2,),
        (3,),
        (4,),
        (5,),
        (6,),
    ]


def test_dataclass_with_list_union_tuples() -> None:
    """Test dataclass containing list of union tuples."""

    @dataclasses.dataclass
    class Config:
        points: List[Union[Tuple[int, int], Tuple[int, int, int]]]
        names: List[str]

    result = tyro.cli(
        Config, args=["--points", "1", "2", "3", "4", "--names", "a", "b"]
    )
    assert result.points == [(1, 2), (3, 4)]
    assert result.names == ["a", "b"]


def test_nested_list_union() -> None:
    def main(x: List[List[Union[int, Tuple[int, str]]]]) -> Any:
        return x

    assert tyro.cli(main, args=["--x", "1", "2", "three", "4"]) == [
        [1, (2, "three"), 4]
    ]


def test_help_message_union_tuples() -> None:
    """Test that help messages show the union options correctly."""

    def main(x: List[Union[Tuple[int, int], Tuple[int, int, int]]]) -> None:
        pass

    # Capture help output.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--help"])
    # The metavar should show both options: {INT INT}|{INT INT INT}.


def test_edge_cases() -> None:
    """Test edge cases for the new functionality."""
    # Empty list.
    assert tyro.cli(List[Union[bool, Tuple[int, int]]], args=[]) == []

    # Single bool.
    assert tyro.cli(List[Union[bool, Tuple[int, int]]], args=["True"]) == [True]
    assert tyro.cli(List[Union[bool, Tuple[int, int]]], args=["False"]) == [False]

    # Single tuple.
    assert tyro.cli(List[Union[bool, Tuple[int, int]]], args=["1", "2"]) == [(1, 2)]

    # Mixed types in specific order.
    assert tyro.cli(
        List[Union[bool, Tuple[int, int]]], args=["1", "2", "True", "3", "4", "False"]
    ) == [(1, 2), True, (3, 4), False]


def test_backtracking_parser() -> None:
    """Test cases that now work with backtracking parser."""

    # Case 1: Input "1 2 3 4 5" with Union[Tuple[int, int], Tuple[int, int, int]].
    # Backtracking finds (1,2), (3,4,5).
    result = tyro.cli(
        List[Union[Tuple[int, int], Tuple[int, int, int]]],
        args=["1", "2", "3", "4", "5"],
    )
    assert result == [(1, 2), (3, 4, 5)]

    # Case 2: Input "1 2 3" with Union[Tuple[int, int], Tuple[int, int, int]].
    # Backtracking finds (1,2,3).
    result = tyro.cli(
        List[Union[Tuple[int, int], Tuple[int, int, int]]], args=["1", "2", "3"]
    )
    assert result == [(1, 2, 3)]

    # Case 3: nargs are sorted, so (3,2) becomes (2,3).
    result = tyro.cli(
        List[Union[Tuple[int, int, int], Tuple[int, int]]],
        args=["1", "2", "3", "4", "5"],
    )
    # With sorted nargs (2,3), backtracking finds (1,2), (3,4,5).
    assert result == [(1, 2), (3, 4, 5)]


def test_truly_unparseable() -> None:
    """Test cases that are truly unparseable even with backtracking."""

    # Case 1: Input "1 2 3 4" with Union[Tuple[int, int, int], Tuple[int, int, int, int, int]].
    # No valid parse exists.
    with pytest.raises(SystemExit):
        tyro.cli(
            List[Union[Tuple[int, int, int], Tuple[int, int, int, int, int]]],
            args=["1", "2", "3", "4"],
        )

    # Case 2: Single element that can't match any option.
    with pytest.raises(SystemExit):
        tyro.cli(List[Union[bool, Tuple[int, int]]], args=["1"])


def test_greedy_parsing_success_1() -> None:
    """Test cases where greedy parsing happens to work."""

    # Works because we try smallest first.
    result = tyro.cli(
        List[Union[Tuple[int], Tuple[int, int], Tuple[int, int, int]]],
        args=["1", "2", "3", "4", "5", "6"],
    )
    assert result == [(1,), (2,), (3,), (4,), (5,), (6,)]


def test_greedy_parsing_success_2() -> None:
    """Test cases where greedy parsing happens to work."""
    # Works because exact multiples.
    result = tyro.cli(
        List[Union[Tuple[int, int], Tuple[int, int, int]]], args=["1", "2", "3", "4"]
    )
    assert result == [(1, 2), (3, 4)]


def test_nested_union_in_collection() -> None:
    """Test nested union in collection."""

    # Works because exact multiples.
    result = tyro.cli(
        List[Union[Tuple[int, int], Union[Tuple[int, int, int], bool]]],
        args=["1", "2", "3", "4"],
    )
    assert result == [(1, 2), (3, 4)]


def f1(x: List[Union[Tuple[int, int], Tuple[int, int, int]]]) -> None:
    """Main function.

    Args:
        x: List of 2D or 3D points.
    """
    pass


def test_helptext_list_union_tuples() -> None:
    """Test that help messages show the union options correctly."""

    helptext = get_helptext_with_checks(f1)
    assert "--x" in helptext
    # Check that the metavar shows both tuple options.
    assert "{INT INT}|{INT INT INT}" in helptext
    assert "List of 2D or 3D points." in helptext


@dataclasses.dataclass
class Config1:
    values: List[Union[bool, Tuple[int, int]]]
    """A list of boolean flags or coordinate pairs."""


def test_helptext_list_bool_or_tuple() -> None:
    """Test helptext for list containing union of bool and tuple."""

    helptext = get_helptext_with_checks(Config1)
    assert "--values" in helptext
    assert "{True,False}|{INT INT}" in helptext
    assert "A list of boolean flags or coordinate pairs." in helptext


@dataclasses.dataclass
class Config2:
    points: List[Union[Tuple[int, int], Tuple[int, int, int]]]
    """List of 2D or 3D points."""
    names: List[str]
    """List of point names."""


def test_helptext_dataclass_with_union_list() -> None:
    """Test helptext for dataclass containing list of union tuples."""

    helptext = get_helptext_with_checks(Config2)
    assert "--points" in helptext
    assert "{INT INT}|{INT INT INT}" in helptext
    assert "List of 2D or 3D points. (required)" in helptext
    assert "--names" in helptext
    assert "List of point names. (required)" in helptext


@dataclasses.dataclass
class Config3:
    points: List[Union[Tuple[int, int], Tuple[int, int, int]]] = dataclasses.field(
        default_factory=lambda: [(1, 2), (3, 4, 5)]
    )
    flags: List[Union[bool, Tuple[int, int]]] = dataclasses.field(
        default_factory=lambda: [True, (10, 20), False]
    )


def test_list_union_with_defaults() -> None:
    """Test list of unions with default values."""

    # Test with defaults.
    result = tyro.cli(Config3, args=[])
    assert result.points == [(1, 2), (3, 4, 5)]
    assert result.flags == [True, (10, 20), False]

    # Test overriding defaults.
    result = tyro.cli(Config3, args=["--points", "5", "6", "7", "--flags", "False"])
    assert result.points == [(5, 6, 7)]
    assert result.flags == [False]

    # Test partial override.
    result = tyro.cli(Config3, args=["--points", "1", "1", "2", "2"])
    assert result.points == [(1, 1), (2, 2)]
    assert result.flags == [True, (10, 20), False]  # Default preserved.


def test_list_union_empty_default() -> None:
    """Test list of unions with empty default."""

    @dataclasses.dataclass
    class Config:
        points: List[Union[Tuple[int, int], Tuple[int, int, int]]] = dataclasses.field(
            default_factory=list
        )

    # Test with empty default.
    result = tyro.cli(Config, args=[])
    assert result.points == []

    # Test adding values.
    result = tyro.cli(Config, args=["--points", "1", "2", "3", "4", "5"])
    assert result.points == [(1, 2), (3, 4, 5)]


def test_function_with_default_list_union() -> None:
    """Test function with default list of unions."""

    def main(
        coords: List[Union[Tuple[int, int], Tuple[int, int, int]]] = [
            (0, 0),
            (1, 1, 1),
        ],
    ) -> List[Union[Tuple[int, int], Tuple[int, int, int]]]:
        return coords

    # Test with default.
    assert tyro.cli(main, args=[]) == [(0, 0), (1, 1, 1)]

    # Test override.
    assert tyro.cli(main, args=["--coords", "2", "3", "4", "5", "6"]) == [
        (2, 3),
        (4, 5, 6),
    ]


@dataclasses.dataclass
class Config4:
    points: List[Union[Tuple[int, int], Tuple[int, int, int]]] = dataclasses.field(
        default_factory=lambda: [(1, 2), (3, 4, 5)]
    )
    """List of 2D or 3D points."""


def test_helptext_with_defaults() -> None:
    """Test helptext shows default values correctly."""

    helptext = get_helptext_with_checks(Config4)
    assert "--points" in helptext
    assert "{INT INT}|{INT INT INT}" in helptext
    assert "List of 2D or 3D points." in helptext
    # Should show it has a default value.
    assert "(default:" in helptext
    # Default values are shown as space-separated integers.
    assert "1 2 3 4 5" in helptext


def test_mixed_type_union_defaults() -> None:
    """Test mixed type unions with defaults."""

    @dataclasses.dataclass
    class Config:
        values: List[Union[str, Tuple[int, int]]] = dataclasses.field(
            default_factory=lambda: ["hello", (1, 2), "world"]
        )

    # Test with default.
    result = tyro.cli(Config, args=[])
    assert result.values == ["hello", (1, 2), "world"]

    # Since str matches greedily, all inputs become strings.
    result = tyro.cli(Config, args=["--values", "5", "6", "test"])
    assert result.values == ["5", "6", "test"]


def test_triple_union_with_defaults() -> None:
    """Test triple union with default values."""

    def main(
        values: List[Union[Tuple[int], Tuple[int, int], Tuple[int, int, int]]] = [
            (1,),
            (2, 3),
            (4, 5, 6),
        ],
    ) -> List[Union[Tuple[int], Tuple[int, int], Tuple[int, int, int]]]:
        return values

    # Test with default.
    assert tyro.cli(main, args=[]) == [(1,), (2, 3), (4, 5, 6)]

    # Test override - greedy parsing means all become single tuples.
    assert tyro.cli(main, args=["--values", "7", "8", "9"]) == [(7,), (8,), (9,)]


def test_tuple_union_direct() -> None:
    """Test direct tuple union: Union[Tuple[int, int], Tuple[int, int, int]]."""
    # Test the direct type annotation as requested.
    assert tyro.cli(Union[Tuple[int, int], Tuple[int, int, int]], args=["5", "5"]) == (
        5,
        5,
    )
    assert tyro.cli(
        Union[Tuple[int, int], Tuple[int, int, int]], args=["5", "5", "2"]
    ) == (
        5,
        5,
        2,
    )

    # Test that invalid argument counts fail.
    with pytest.raises(SystemExit):
        tyro.cli(
            Union[Tuple[int, int], Tuple[int, int, int]], args=["5", "5", "2", "1"]
        )
    with pytest.raises(SystemExit):
        tyro.cli(Union[Tuple[int, int], Tuple[int, int, int]], args=["5"])
    with pytest.raises(SystemExit):
        tyro.cli(Union[Tuple[int, int], Tuple[int, int, int]], args=[])
