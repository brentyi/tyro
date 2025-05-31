"""Test dict with variable-length values using backtracking."""

from typing import Annotated, Dict, Tuple

import tyro
from tyro.conf import UseAppendAction


def test_dict_with_union_values():
    """Test Dict[str, int| Tuple[int, int]]."""

    def main(
        values: Dict[str, int | Tuple[int, int]],
    ) -> Dict[str, int | Tuple[int, int]]:
        return values

    # Single value.
    assert tyro.cli(main, args=["--values", "a", "1"]) == {"a": 1}

    # Tuple value.
    assert tyro.cli(main, args=["--values", "b", "2", "3"]) == {"b": (2, 3)}

    # Mixed values.
    assert tyro.cli(main, args=["--values", "a", "1", "b", "2", "3"]) == {
        "a": 1,
        "b": (2, 3),
    }

    # Multiple mixed values.
    assert tyro.cli(main, args=["--values", "a", "1", "b", "2", "3", "c", "4"]) == {
        "a": 1,
        "b": (2, 3),
        "c": 4,
    }

    # Multiple tuple values.
    assert tyro.cli(main, args=["--values", "x", "1", "2", "y", "3", "4"]) == {
        "x": (1, 2),
        "y": (3, 4),
    }


def test_dict_with_union_values_append():
    """Test Dict[str, int| Tuple[int, int]] with append action."""

    def main(
        values: Annotated[Dict[str, int | Tuple[int, int]], UseAppendAction],
    ) -> Dict[str, int | Tuple[int, int]]:
        return values

    # Single value multiple times.
    assert tyro.cli(main, args=["--values", "a", "1", "--values", "b", "2", "3"]) == {
        "a": 1,
        "b": (2, 3),
    }

    # Multiple append operations.
    result = tyro.cli(
        main,
        args=["--values", "x", "1", "--values", "y", "2", "3", "--values", "z", "4"],
    )
    assert result == {"x": 1, "y": (2, 3), "z": 4}


def test_dict_with_union_three_options():
    """Test Dict with union of three different lengths."""

    def main(
        values: Dict[str, int | Tuple[int, int] | Tuple[int, int, int]],
    ) -> Dict[str, int | Tuple[int, int] | Tuple[int, int, int]]:
        return values

    # Test all three options.
    assert tyro.cli(main, args=["--values", "a", "1"]) == {"a": 1}
    assert tyro.cli(main, args=["--values", "b", "2", "3"]) == {"b": (2, 3)}
    # This parses as two pairs: key="c" value=4, key="5" value=6.
    assert tyro.cli(main, args=["--values", "c", "4", "5", "6"]) == {"c": 4, "5": 6}

    # The backtracking parser will still try shorter matches first and find valid parses.
    # This is expected behavior - the parser tries options in the order they appear.


def test_dict_complex_value_types():
    """Test dict with more complex union types."""

    def main(
        mapping: Dict[str, float | Tuple[float, str]],
    ) -> Dict[str, float | Tuple[float, str]]:
        return mapping

    # Single float.
    assert tyro.cli(main, args=["--mapping", "x", "1.5"]) == {"x": 1.5}

    # Tuple of float and string.
    assert tyro.cli(main, args=["--mapping", "y", "2.5", "hello"]) == {
        "y": (2.5, "hello")
    }

    # Mixed.
    result = tyro.cli(main, args=["--mapping", "a", "1.0", "b", "2.0", "world"])
    assert result == {"a": 1.0, "b": (2.0, "world")}


def test_dict_int_keys_variable_string_values():
    """Test dict with integer keys and variable-length string values."""

    def main(
        mapping: Dict[int, str | Tuple[str, str]],
    ) -> Dict[int, str | Tuple[str, str]]:
        return mapping

    # Single string value.
    assert tyro.cli(main, args=["--mapping", "1", "hello"]) == {1: "hello"}

    # Tuple of strings.
    assert tyro.cli(main, args=["--mapping", "2", "hello", "world"]) == {
        2: ("hello", "world")
    }

    # Mixed.
    result = tyro.cli(main, args=["--mapping", "1", "foo", "2", "bar", "baz"])
    assert result == {1: "foo", 2: ("bar", "baz")}


def test_dict_union_keys():
    """Test dict with union types in keys."""

    def main(
        mapping: Dict[int | Tuple[int, int], str],
    ) -> Dict[int | Tuple[int, int], str]:
        return mapping

    # Single int key.
    assert tyro.cli(main, args=["--mapping", "1", "hello"]) == {1: "hello"}

    # Tuple key.
    assert tyro.cli(main, args=["--mapping", "2", "3", "world"]) == {(2, 3): "world"}

    # Mixed.
    result = tyro.cli(main, args=["--mapping", "1", "foo", "2", "3", "bar"])
    assert result == {1: "foo", (2, 3): "bar"}


def test_dict_union_keys_and_values():
    """Test dict with union types in both keys and values."""

    def main(
        mapping: Dict[str | Tuple[str, str], int | Tuple[int, int]],
    ) -> Dict[str | Tuple[str, str], int | Tuple[int, int]]:
        return mapping

    # Simple key and value.
    assert tyro.cli(main, args=["--mapping", "a", "1"]) == {"a": 1}

    # Simple key, tuple value.
    assert tyro.cli(main, args=["--mapping", "b", "2", "3"]) == {"b": (2, 3)}

    # Tuple key, simple value.
    assert tyro.cli(main, args=["--mapping", "c", "d", "4"]) == {("c", "d"): 4}

    # Tuple key, tuple value.
    assert tyro.cli(main, args=["--mapping", "e", "f", "5", "6"]) == {
        ("e", "f"): (5, 6)
    }

    # Mixed cases.
    result = tyro.cli(
        main, args=["--mapping", "a", "1", "b", "c", "2", "d", "e", "3", "4"]
    )
    # The parser processes left to right.
    # - "a" (str key), "1" (int value) → {"a": 1}
    # - "b", "c" (tuple key), "2" (int value) → {("b", "c"): 2}
    # - "d", "e" (tuple key), "3", "4" (tuple value) → {("d", "e"): (3, 4)}
    assert result == {"a": 1, ("b", "c"): 2, ("d", "e"): (3, 4)}
