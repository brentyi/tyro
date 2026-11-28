"""Tests for nested calls, concurrent calls, and object lifetimes."""

import dataclasses
import gc
import pickle
import subprocess
import sys
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Generic, List, Optional, TypeVar

import pytest

import tyro
from tyro.constructors import (
    ConstructorRegistry,
    PrimitiveConstructorSpec,
    PrimitiveTypeInfo,
)

T = TypeVar("T")


@dataclasses.dataclass
class GenericStruct(Generic[T]):
    x: T


def test_concurrent_generics() -> None:
    @dataclasses.dataclass
    class IntConfig:
        g: GenericStruct[int]

    @dataclasses.dataclass
    class StrConfig:
        g: GenericStruct[str]

    def call(i: int) -> Any:
        return tyro.cli((IntConfig, StrConfig)[i % 2], args=["--g.x", "3"]).g.x  # type: ignore

    old_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        with ThreadPoolExecutor(8) as executor:
            outputs = list(executor.map(call, range(300)))
    finally:
        sys.setswitchinterval(old_interval)
    assert outputs == [(3, "3")[i % 2] for i in range(300)]


def test_overlapping_call_lifetimes() -> None:
    """A slow call in one thread shouldn't keep objects from other threads alive, or
    result in stale annotations."""
    inside = threading.Event()
    done = threading.Event()

    def slow_factory() -> int:
        inside.set()
        done.wait(10.0)
        return 3

    @dataclasses.dataclass
    class Slow:
        x: int = dataclasses.field(default_factory=slow_factory)

    def make() -> Any:
        @dataclasses.dataclass
        class Config:
            x: Optional[int] = 1

        return Config

    thread = threading.Thread(target=lambda: tyro.cli(Slow, args=[]))
    thread.start()
    inside.wait(10.0)
    try:
        refs = []
        for _ in range(5):
            cls = make()
            refs.append(weakref.ref(cls))
            tyro.cli(cls, args=[])
            del cls
        gc.collect()
        assert all(ref() is None for ref in refs)

        cls = make()
        tyro.cli(cls, args=[])
        cls.__annotations__["x"] = str
        assert tyro.cli(cls, args=["--x", "a"]).x == "a"
    finally:
        done.set()
        thread.join()


def test_finalizer_can_call_tyro() -> None:
    """Run in a subprocess, because failure is a deadlock."""
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import tyro
from tyro import _unsafe_cache
class Finalized:
    def __del__(self):
        tyro.cli(int, args=["5"])
cache = _unsafe_cache.make_cache()
def main(x: int = 3):
    return x
with _unsafe_cache.cache_scope():
    cache["x"] = Finalized()
assert tyro.cli(main, args=[]) == 3
""",
        ],
        check=True,
        timeout=60,
    )


def test_stacks_are_unwound() -> None:
    from tyro import _fields, _unsafe_cache

    stack = _fields._combined_context_markers.stack
    length = len(stack)
    with _unsafe_cache.cache_scope():
        stack.append(frozenset())  # Never popped.
    assert len(stack) == length


def test_rule_added_to_default_registry() -> None:
    def main(x: str = "a") -> str:
        return x

    assert tyro.cli(main, args=["--x", "b"]) == "b"
    registry = ConstructorRegistry._active_registries[0]
    spec = ConstructorRegistry.get_primitive_spec(PrimitiveTypeInfo.make(str, set()))
    assert isinstance(spec, PrimitiveConstructorSpec)
    spec = dataclasses.replace(spec, instance_from_str=lambda args: "X" + args[0])
    registry.primitive_rule(lambda info: spec if info.type is str else None)
    try:
        assert tyro.cli(main, args=["--x", "b"]) == "Xb"
    finally:
        registry._primitive_rules.pop()
    assert tyro.cli(main, args=["--x", "b"]) == "b"


def test_union_error_repr_and_pickle() -> None:
    spec = ConstructorRegistry.get_primitive_spec(
        PrimitiveTypeInfo.make(int | bool, set())  # type: ignore
    )
    assert isinstance(spec, PrimitiveConstructorSpec)
    with pytest.raises(ValueError) as info:
        spec.instance_from_str(["abc"])
    assert "abc" in repr(info.value)
    assert str(pickle.loads(pickle.dumps(info.value))) == str(info.value)


def test_nested_call() -> None:
    def factory() -> List[int]:
        return tyro.cli(List[int], args=["1", "2"])

    @dataclasses.dataclass
    class Config:
        x: List[int] = dataclasses.field(default_factory=factory)
        y: Optional[int] = None

    assert tyro.cli(Config, args=["--y", "3"]) == Config([1, 2], 3)


def test_concurrent_delimiters() -> None:
    def main(a_b: int) -> int:
        return a_b

    def call(i: int) -> Any:
        return tyro.cli(
            main,
            args=["--a_b" if i % 2 else "--a-b", "3"],
            use_underscores=i % 3 == 0,
        )

    old_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        with ThreadPoolExecutor(8) as executor:
            assert list(executor.map(call, range(300))) == [3] * 300
    finally:
        sys.setswitchinterval(old_interval)


def test_help_does_not_keep_classes_alive() -> None:
    def make() -> Any:
        @dataclasses.dataclass
        class Config:
            """Docstring."""

            x: int = 1
            """Helptext."""

        return Config

    refs = []
    for _ in range(5):
        cls = make()
        refs.append(weakref.ref(cls))
        with pytest.raises(SystemExit) as info:
            tyro.cli(cls, args=["--help"])
        del cls, info
    gc.collect()
    # The most recent class can be referenced by frames in the traceback.
    assert sum(ref() is not None for ref in refs) <= 1
