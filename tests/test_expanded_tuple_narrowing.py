from __future__ import annotations

import dataclasses
from typing import Any

from helptext_utils import get_helptext_with_checks

import tyro


def test_recursive_tuple_narrowing():
    """Test recursive narrowing of nested tuple types."""

    def fn(
        w: Any = (1, 2, 3),
        x: Any = (1, 2, (3, "4", 5)),
        y: tuple[int, int, Any] = (1, 2, (3, 4, 5)),
        z: tuple[int, int, tuple[int, str, int]] = (1, 2, (3, "4", 5)),
    ) -> Any:
        return w, x, y, z

    # Test CLI parsing with nested tuples
    result = tyro.cli(
        fn,
        args="--w 6 7 8 --x 9 10 11 twelve 13 --y.0 14 --y.1 15 --y.2 16 17 18 --z 19 20 21 hello 23".split(),
    )

    helptext = get_helptext_with_checks(fn)
    assert "--w [INT [INT ...]" in helptext
    assert "--x INT INT INT STR INT" in helptext
    assert "--y.0 INT" in helptext
    assert "--y.1 INT" in helptext
    assert "--y.2 [INT [INT ...]]" in helptext
    assert "--z INT INT INT STR INT" in helptext

    # Simple tuple
    assert result[0] == (6, 7, 8)

    # Nested tuple with Any
    assert result[1] == (9, 10, (11, "twelve", 13))
    assert isinstance(result[1][0], int)
    assert isinstance(result[1][1], int)
    assert isinstance(result[1][2], tuple)
    assert isinstance(result[1][2][0], int)
    assert isinstance(result[1][2][1], str)
    assert isinstance(result[1][2][2], int)

    # Tuple with specified types but Any for the nested part
    assert result[2] == (14, 15, (16, 17, 18))
    assert isinstance(result[2][0], int)
    assert isinstance(result[2][1], int)
    assert isinstance(result[2][2], tuple)

    # Tuple with fully specified nested types
    assert result[3] == (19, 20, (21, "hello", 23))
    assert isinstance(result[3][0], int)
    assert isinstance(result[3][1], int)
    assert isinstance(result[3][2], tuple)
    assert isinstance(result[3][2][0], int)
    assert isinstance(result[3][2][1], str)
    assert isinstance(result[3][2][2], int)


def test_tuple_homogeneous_narrowing():
    """Test narrowing of homogeneous tuples."""

    def fn(
        x: Any = (1, 2, 3),
        y: tuple[Any, ...] = (1, 2, 3),
    ) -> Any:
        return x, y

    result = tyro.cli(fn, args="--x 4 5 6 --y 7 8 9 10".split())

    # Both tuples should be properly narrowed and parsed
    assert result[0] == (4, 5, 6)
    assert result[1] == (7, 8, 9, 10)


def test_mixed_tuple_types():
    """Test narrowing with mixed tuple element types."""

    def fn(
        x: Any = (1, "two", 3.0),
        y: tuple[int, Any, float] = (1, "two", 3.0),
    ) -> Any:
        return x, y

    result = tyro.cli(fn, args="--x 4 five 6.0 --y 7 eight 9.0".split())

    assert result[0] == (4, "five", 6.0)
    assert isinstance(result[0][0], int)
    assert isinstance(result[0][1], str)
    assert isinstance(result[0][2], float)

    assert result[1] == (7, "eight", 9.0)
    assert isinstance(result[1][0], int)
    assert isinstance(result[1][1], str)
    assert isinstance(result[1][2], float)


def test_partial_tuple_narrowing():
    """Test that we can narrow tuple types with partially specified types."""

    @dataclasses.dataclass
    class Config:
        x: tuple[int, int, Any] = (1, 2, "hello")
        y: tuple[int, Any, float] = (1, "world", 3.0)

    result = tyro.cli(Config, args="--x 4 5 six --y 7 eight 9.0".split())

    assert result.x == (4, 5, "six")
    assert result.y == (7, "eight", 9.0)
    assert isinstance(result.y[0], int)
    assert isinstance(result.y[1], str)
    assert isinstance(result.y[2], float)
