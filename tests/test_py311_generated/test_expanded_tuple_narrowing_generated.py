from typing import Any, Tuple

import tyro
from tyro._resolver import narrow_collection_types


def test_recursive_tuple_narrowing():
    """Test recursive narrowing of nested tuple types."""

    def fn(
        x: Any = (1, 2, (3, "4", 5)),
        y: tuple[int, int, Any] = (1, 2, (3, 4, 5)),
        z: tuple[int, int, tuple[int, str, int]] = (1, 2, (3, "4", 5)),
    ) -> Any:
        return x, y, z

    # Test CLI parsing with nested tuples
    result = tyro.cli(
        fn, args="--x 6 7 8 9 10 --y 11 12 13 14 15 --z 16 17 18 hello 20".split()
    )

    # The first tuple should be parsed with proper types
    assert result[0] == (6, 7, (8, "9", 10))
    assert isinstance(result[0][0], int)
    assert isinstance(result[0][1], int)
    assert isinstance(result[0][2], tuple)
    assert isinstance(result[0][2][0], int)
    assert isinstance(result[0][2][1], str)
    assert isinstance(result[0][2][2], int)

    # The second tuple should have types preserved but narrowed Any
    assert result[1] == (11, 12, (13, 14, 15))
    assert isinstance(result[1][0], int)
    assert isinstance(result[1][1], int)
    assert isinstance(result[1][2], tuple)

    # The third tuple should have explicitly defined types
    assert result[2] == (16, 17, (18, "hello", 20))
    assert isinstance(result[2][0], int)
    assert isinstance(result[2][1], int)
    assert isinstance(result[2][2], tuple)
    assert isinstance(result[2][2][0], int)
    assert isinstance(result[2][2][1], str)
    assert isinstance(result[2][2][2], int)


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


def test_direct_narrow_collection_types():
    """Test the narrow_collection_types function directly."""

    # Test narrowing Any with tuple default
    narrowed = narrow_collection_types(Any, (1, 2, 3))
    assert narrowed == Tuple[int, int, int]

    # Test narrowing tuple[Any, ...] with default
    narrowed = narrow_collection_types(Tuple[Any, ...], (1, 2, 3))
    assert narrowed == Tuple[int, ...]

    # Test narrowing tuple with mixed types
    narrowed = narrow_collection_types(Any, (1, "two", 3.0))
    assert narrowed == Tuple[int, str, float]

    # Test narrowing with nested tuple
    narrowed = narrow_collection_types(Any, (1, (2, "3"), 4.0))
    assert narrowed == Tuple[int, Tuple[int, str], float]

    # Test narrowing tuple with explicit types and Any
    t_type = Tuple[int, Any, float]
    default = (1, "two", 3.0)
    narrowed = narrow_collection_types(t_type, default)
    assert narrowed == Tuple[int, str, float]
