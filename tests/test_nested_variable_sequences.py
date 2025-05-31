"""Test nested variable-length sequences with backtracking support."""

from typing import List, Tuple

from typing_extensions import Annotated

import tyro
from tyro.conf import UseAppendAction


def test_list_of_lists_no_append():
    """Test List[List[str]] without UseAppendAction.

    All arguments are consumed into a single inner list.
    """

    def main(values: List[List[str]]) -> List[List[str]]:
        return values

    # All args go into one inner list.
    result = tyro.cli(main, args=["--values", "a", "b", "c", "d", "e"])
    assert result == [["a", "b", "c", "d", "e"]]


def test_list_of_lists_with_append():
    """Test List[List[str]] with UseAppendAction.

    Each --values flag creates a separate inner list.
    """

    def main(values: Annotated[List[List[str]], UseAppendAction]) -> List[List[str]]:
        return values

    # Each --values creates a new inner list.
    result = tyro.cli(main, args=["--values", "a", "b", "--values", "c", "d", "e"])
    assert result == [["a", "b"], ["c", "d", "e"]]

    # Single flag usage.
    result2 = tyro.cli(main, args=["--values", "x", "y", "z"])
    assert result2 == [["x", "y", "z"]]


def test_list_of_lists_of_ints():
    """Test List[List[int]] with UseAppendAction."""

    def main(values: Annotated[List[List[int]], UseAppendAction]) -> List[List[int]]:
        return values

    result = tyro.cli(main, args=["--values", "1", "2", "--values", "3", "4", "5"])
    assert result == [[1, 2], [3, 4, 5]]


def test_list_of_tuples_with_append():
    """Test List[Tuple[str, int]] with UseAppendAction."""

    def main(
        values: Annotated[List[Tuple[str, int]], UseAppendAction],
    ) -> List[Tuple[str, int]]:
        return values

    result = tyro.cli(main, args=["--values", "a", "1", "--values", "b", "2"])
    assert result == [("a", 1), ("b", 2)]


def test_list_of_variable_tuples():
    """Test List[Tuple[int, ...]] with UseAppendAction."""

    def main(
        values: Annotated[List[Tuple[int, ...]], UseAppendAction],
    ) -> List[Tuple[int, ...]]:
        return values

    # Variable-length tuples.
    result = tyro.cli(main, args=["--values", "1", "2", "--values", "3", "4", "5", "6"])
    assert result == [(1, 2), (3, 4, 5, 6)]

    # Single element tuple.
    result2 = tyro.cli(main, args=["--values", "7"])
    assert result2 == [(7,)]


def test_list_of_unions():
    """Test List[Union[int, Tuple[int, int]]] with UseAppendAction."""
    from typing import Union

    def main(
        values: Annotated[List[Union[int, Tuple[int, int]]], UseAppendAction],
    ) -> List[Union[int, Tuple[int, int]]]:
        return values

    # Mix of single ints and tuples.
    result = tyro.cli(
        main, args=["--values", "1", "--values", "2", "3", "--values", "4"]
    )
    assert result == [1, (2, 3), 4]
