"""Tests for collections containing unions with different fixed nargs.

This tests the functionality added to support types like:
- List[Union[bool, Tuple[int, int]]]
- List[Union[Tuple[int, int], Tuple[int, int, int]]]
"""

import dataclasses
from typing import List, Tuple, Union

import pytest

import tyro


def test_list_bool_or_tuple() -> None:
    """Test list containing union of bool and fixed-size tuple."""
    # Test case from variable_length_nested_seq.py
    assert tyro.cli(list[bool | tuple[int, int]], args="3 4 5 6".split(" ")) == [
        (3, 4),
        (5, 6),
    ]
    assert tyro.cli(
        list[bool | tuple[int, int]], args="True 3 4 5 6 False".split(" ")
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

    # The greedy parsing means some combinations won't work (e.g., odd numbers).
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--x", "1", "2", "3"])


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
    # and the parsing tries options from left to right
    assert tyro.cli(main, args=["--x", "hello", "1", "2", "world"]) == [
        "hello",
        "1",
        "2",
        "world",
    ]
    assert tyro.cli(main, args=["--x", "1", "2", "3", "4"]) == ["1", "2", "3", "4"]

    # Even with tuple first, strings that can be parsed as strings will be
    def main2(
        x: List[Union[Tuple[int, int], str]],
    ) -> List[Union[Tuple[int, int], str]]:
        return x

    # When all args can be parsed as strings, they will be
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

    # Should parse greedily, trying single int first
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


def test_nested_list_union_not_supported() -> None:
    """Test that nested variable-length sequences still require UseAppendAction."""
    from tyro.constructors._primitive_spec import UnsupportedTypeAnnotationError

    def main(x: List[List[Union[int, Tuple[int, int]]]]) -> None:
        pass

    # This should still fail because we have nested variable-length sequences
    with pytest.raises(UnsupportedTypeAnnotationError) as e:
        tyro.cli(main, args=["--help"])
    assert "variable-length sequences" in str(e.value)


def test_help_message_union_tuples() -> None:
    """Test that help messages show the union options correctly."""

    def main(x: List[Union[Tuple[int, int], Tuple[int, int, int]]]) -> None:
        pass

    # Capture help output
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--help"])
    # The metavar should show both options: {INT INT}|{INT INT INT}


def test_edge_cases() -> None:
    """Test edge cases for the new functionality."""
    # Empty list
    assert tyro.cli(List[Union[bool, Tuple[int, int]]], args=[]) == []

    # Single bool
    assert tyro.cli(List[Union[bool, Tuple[int, int]]], args=["True"]) == [True]
    assert tyro.cli(List[Union[bool, Tuple[int, int]]], args=["False"]) == [False]

    # Single tuple
    assert tyro.cli(List[Union[bool, Tuple[int, int]]], args=["1", "2"]) == [(1, 2)]

    # Mixed types in specific order
    assert tyro.cli(
        List[Union[bool, Tuple[int, int]]], args=["1", "2", "True", "3", "4", "False"]
    ) == [(1, 2), True, (3, 4), False]
