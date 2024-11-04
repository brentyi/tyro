import dataclasses
import pathlib
from typing import Any, Dict, List, Tuple

from tyro._fields import is_struct_type
from tyro._singleton import MISSING_NONPROP


def test_is_struct_type_simple():
    assert not is_struct_type(int, MISSING_NONPROP)
    assert not is_struct_type(bool, MISSING_NONPROP)
    assert not is_struct_type(str, MISSING_NONPROP)
    assert not is_struct_type(pathlib.Path, MISSING_NONPROP)


def test_is_struct_type_containers():
    assert not is_struct_type(List[int], MISSING_NONPROP)
    assert not is_struct_type(List[bool], MISSING_NONPROP)
    assert not is_struct_type(List[str], MISSING_NONPROP)
    assert not is_struct_type(List[pathlib.Path], MISSING_NONPROP)


@dataclasses.dataclass
class Color:
    r: int
    g: int
    b: int


def test_is_struct_type_actually_struct():
    assert is_struct_type(Color, Color(255, 0, 0))


def test_is_struct_type_actually_struct_narrowing():
    assert is_struct_type(Any, Color(255, 0, 0))
    assert is_struct_type(object, Color(255, 0, 0))
    assert not is_struct_type(int, Color(255, 0, 0))


def test_is_struct_type_actually_struct_in_container():
    assert is_struct_type(Tuple[Color, Color], MISSING_NONPROP)
    assert is_struct_type(Tuple[object, ...], (Color(255, 0, 0),))
    assert is_struct_type(Tuple[Any, ...], (Color(255, 0, 0),))
    assert is_struct_type(tuple, (Color(255, 0, 0),))
    assert not is_struct_type(tuple, (1, 2, 3))
    assert is_struct_type(tuple, (1, Color(255, 0, 0), 3))
    assert is_struct_type(List[Any], [Color(255, 0, 0)])


def test_struct_dict():
    assert is_struct_type(Dict[str, int], {"x": 5})
    assert is_struct_type(dict, {"x": 5})
    assert is_struct_type(Any, {"x": 5})
