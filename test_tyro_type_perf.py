#!/usr/bin/env python3
"""Quick performance test to verify TyroType functions are faster."""

import time
from typing import Union

from src.tyro._resolver import (
    expand_union_types,
    expand_union_types_NEW,
    narrow_collection_types,
    narrow_collection_types_NEW,
)
from src.tyro._tyro_type import type_to_tyro_type


def test_narrow_collection_old():
    """Test OLD narrow_collection_types with reconstruction."""
    typ = list
    default = [1, "hello", 3.14, True, "world"] * 100  # 500 elements

    start = time.perf_counter()
    for _ in range(1000):
        result = narrow_collection_types(typ, default)
    duration = time.perf_counter() - start

    print(f"OLD narrow_collection_types: {duration:.4f}s")
    return duration


def test_narrow_collection_new():
    """Test NEW narrow_collection_types_NEW without reconstruction."""
    typ_raw = list
    default = [1, "hello", 3.14, True, "world"] * 100  # 500 elements

    start = time.perf_counter()
    for _ in range(1000):
        typ = type_to_tyro_type(typ_raw)  # Include conversion in timing
        result = narrow_collection_types_NEW(typ, default)
    duration = time.perf_counter() - start

    print(f"NEW narrow_collection_types_NEW (with conversion): {duration:.4f}s")
    return duration


def test_expand_union_old():
    """Test OLD expand_union_types with reconstruction."""
    typ = Union[int, str]
    default = 3.14  # Will expand to include float

    start = time.perf_counter()
    for _ in range(10000):
        result = expand_union_types(typ, default)
    duration = time.perf_counter() - start

    print(f"OLD expand_union_types: {duration:.4f}s")
    return duration


def test_expand_union_new():
    """Test NEW expand_union_types_NEW without reconstruction."""
    typ_raw = Union[int, str]
    default = 3.14  # Will expand to include float

    start = time.perf_counter()
    for _ in range(10000):
        typ = type_to_tyro_type(typ_raw)  # Include conversion in timing
        result = expand_union_types_NEW(typ, default)
    duration = time.perf_counter() - start

    print(f"NEW expand_union_types_NEW (with conversion): {duration:.4f}s")
    return duration


if __name__ == "__main__":
    print("Testing narrow_collection_types performance:")
    old_narrow = test_narrow_collection_old()
    new_narrow = test_narrow_collection_new()
    speedup_narrow = old_narrow / new_narrow
    print(f"Speedup: {speedup_narrow:.2f}x\n")

    print("Testing expand_union_types performance:")
    old_expand = test_expand_union_old()
    new_expand = test_expand_union_new()
    speedup_expand = old_expand / new_expand
    print(f"Speedup: {speedup_expand:.2f}x\n")

    print(f"Overall average speedup: {(speedup_narrow + speedup_expand) / 2:.2f}x")
