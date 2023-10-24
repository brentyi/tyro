import dataclasses
import pathlib
from typing import Any, Dict, List, Tuple

from tyro._fields import MISSING_NONPROP, is_nested_type


def test_is_nested_type_simple():
    assert not is_nested_type(int, MISSING_NONPROP)
    assert not is_nested_type(bool, MISSING_NONPROP)
    assert not is_nested_type(str, MISSING_NONPROP)
    assert not is_nested_type(pathlib.Path, MISSING_NONPROP)


def test_is_nested_type_containers():
    assert not is_nested_type(List[int], MISSING_NONPROP)
    assert not is_nested_type(List[bool], MISSING_NONPROP)
    assert not is_nested_type(List[str], MISSING_NONPROP)
    assert not is_nested_type(List[pathlib.Path], MISSING_NONPROP)


@dataclasses.dataclass
class Color:
    r: int
    g: int
    b: int


def test_is_nested_type_actually_nested():
    assert is_nested_type(Color, Color(255, 0, 0))


def test_is_nested_type_actually_nested_narrowing():
    assert is_nested_type(Any, Color(255, 0, 0))
    assert is_nested_type(object, Color(255, 0, 0))
    assert not is_nested_type(int, Color(255, 0, 0))


def test_is_nested_type_actually_nested_in_container():
    assert is_nested_type(Tuple[Color, Color], MISSING_NONPROP)
    assert is_nested_type(Tuple[object, ...], (Color(255, 0, 0),))
    assert is_nested_type(Tuple[Any, ...], (Color(255, 0, 0),))
    assert is_nested_type(tuple, (Color(255, 0, 0),))
    assert not is_nested_type(tuple, (1, 2, 3))
    assert is_nested_type(tuple, (1, Color(255, 0, 0), 3))
    assert is_nested_type(List[Any], [Color(255, 0, 0)])


def test_nested_dict():
    assert is_nested_type(Dict[str, int], {"x": 5})
    assert is_nested_type(dict, {"x": 5})
    assert is_nested_type(Any, {"x": 5})
