"""Caching utilities. All caches in this module are scoped to a single `tyro.cli()` call."""

import _thread
import contextlib
import types
from typing import Any, Dict, List

_cache_list: List[Dict[Any, Any]] = []


def clear_cache() -> None:
    for c in _cache_list:
        c.clear()


class ThreadLocalStack(_thread._local):
    """Stack that isn't shared between threads."""

    def __init__(self, *initial: Any) -> None:
        self.stack: List[Any] = list(initial)


_stacks: List[ThreadLocalStack] = []


def make_thread_local_stack(*initial: Any) -> ThreadLocalStack:
    """Make a stack that will be unwound when `tyro.cli()` exits."""
    out = ThreadLocalStack(*initial)
    _stacks.append(out)
    return out


@contextlib.contextmanager
def cache_scope():
    """Context for a `tyro.cli()` call. Clears caches when we enter and exit.

    Calls can be nested or concurrent, so caches can be cleared while they're being used.
    This is safe: it can only result in cache misses. We intentionally don't use any locks,
    because deallocating objects can run arbitrary code, including `tyro.cli()`."""
    # Make sure we start on a clean slate.
    clear_cache()
    stack_lengths = [len(s.stack) for s in _stacks]
    try:
        yield
    finally:
        # Context managers aren't guaranteed to be balanced if they're interrupted, for
        # example by a KeyboardInterrupt.
        for s, length in zip(_stacks, stack_lengths):
            del s.stack[length:]
        # Prevent unnecessary memory usage.
        clear_cache()


def make_cache() -> Dict[Any, Any]:
    """Make a dictionary that will be cleared at the start and end of each
    `tyro.cli()` call."""
    cache: Dict[Any, Any] = {}
    _cache_list.append(cache)
    return cache


_GenericAlias: Any = getattr(types, "GenericAlias", None)
_UnionType: Any = getattr(types, "UnionType", None)


def _id_key_function(obj: Any) -> None: ...


def id_key(obj: Any) -> Any:
    """Make a key that compares objects by identity. The key holds a reference, so the ID
    of the object can't be reused while the key is in a cache.

    Bound methods are hashed and compared using the identity of `__self__`, and unlike an
    equivalent class are implemented in C."""
    # Methods can't be bound to None.
    return None if obj is None else types.MethodType(_id_key_function, obj)


def type_key(typ: Any) -> Any:
    """Get a key for a type annotation. Types with the same key are interchangeable.

    Hash-based equality is not sufficient for annotations. For example, `Union[int, str]
    == Union[str, int]` and `Literal[1, 2] == Literal[2, 1]`, but the order of arguments
    will impact parsing.

    We instead rely on object identity. Annotations created by subscripting objects in
    `typing` are interned by `typing`, so repeated annotations will usually share a key.
    `list[int]` and `int | str` are not interned, so we handle these structurally."""
    cls = type(typ)
    if cls is type:
        # Fast path. Note that metaclasses can override equality.
        return typ
    if cls is _GenericAlias or cls is _UnionType:
        return (
            cls,
            getattr(typ, "__origin__", None),
            getattr(typ, "__unpacked__", False),
            tuple([type_key(arg) for arg in typ.__args__]),
        )
    return id_key(typ)


def hashable_key(obj: Any) -> Any:
    """Get a key that uses hash-based equality if possible, and identity otherwise."""
    try:
        hash(obj)
        return obj
    except TypeError:
        return id_key(obj)
