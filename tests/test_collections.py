import dataclasses
from typing import List, Optional, Sequence, Set, Tuple

import pytest

import dcargs


def test_tuples_fixed():
    @dataclasses.dataclass
    class A:
        x: Tuple[int, int, int]

    assert dcargs.parse(A, args=["--x", "1", "2", "3"]) == A(x=(1, 2, 3))
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=[])


def test_tuples_fixed_multitype():
    @dataclasses.dataclass
    class A:
        x: Tuple[int, str, float]

    assert dcargs.parse(A, args=["--x", "1", "2", "3.5"]) == A(x=(1, "2", 3.5))
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=[])


def test_tuples_fixed_bool():
    @dataclasses.dataclass
    class A:
        x: Tuple[bool, bool, bool]

    assert dcargs.parse(A, args=["--x", "True", "True", "False"]) == A(
        x=(True, True, False)
    )
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=[])


def test_tuples_variable():
    @dataclasses.dataclass
    class A:
        x: Tuple[int, ...]

    assert dcargs.parse(A, args=["--x", "1", "2", "3"]) == A(x=(1, 2, 3))
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=[])


def test_tuples_variable_bool():
    @dataclasses.dataclass
    class A:
        x: Tuple[bool, ...]

    assert dcargs.parse(A, args=["--x", "True", "True", "False"]) == A(
        x=(True, True, False)
    )
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=[])


def test_tuples_variable_optional():
    @dataclasses.dataclass
    class A:
        x: Optional[Tuple[int, ...]]

    assert dcargs.parse(A, args=["--x", "1", "2", "3"]) == A(x=(1, 2, 3))
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    assert dcargs.parse(A, args=[]) == A(x=None)


def test_sequences():
    @dataclasses.dataclass
    class A:
        x: Sequence[int]

    assert dcargs.parse(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=[])


def test_lists():
    @dataclasses.dataclass
    class A:
        x: List[int]

    assert dcargs.parse(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=[])


def test_lists_bool():
    @dataclasses.dataclass
    class A:
        x: List[bool]

    assert dcargs.parse(A, args=["--x", "True", "False", "True"]) == A(
        x=[True, False, True]
    )
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=[])


def test_sets():
    @dataclasses.dataclass
    class A:
        x: Set[int]

    assert dcargs.parse(A, args=["--x", "1", "2", "3", "3"]) == A(x={1, 2, 3})
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=[])


def test_optional_sequences():
    @dataclasses.dataclass
    class A:
        x: Optional[Sequence[int]]

    assert dcargs.parse(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    assert dcargs.parse(A, args=[]) == A(x=None)


def test_optional_lists():
    @dataclasses.dataclass
    class A:
        x: Optional[List[int]]

    assert dcargs.parse(A, args=["--x", "1", "2", "3"]) == A(x=[1, 2, 3])
    with pytest.raises(SystemExit):
        dcargs.parse(A, args=["--x"])
    assert dcargs.parse(A, args=[]) == A(x=None)
