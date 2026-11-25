"""Caching utilities. All caches in this module are scoped to a single `tyro.cli()` call."""

import _thread
import functools
import sys
import types
from typing import Any, Callable, Dict, List, TypeVar

CallableType = TypeVar("CallableType", bound=Callable)


_cache_list: List[Dict[Any, Any]] = []


def clear_cache() -> None:
    for c in _cache_list:
        c.clear()


_scope_lock = _thread.allocate_lock()
_scope_depth = 0


class cache_scope:
    """Context manager for a `tyro.cli()` call. Caches are cleared when we enter the first
    scope and when we exit the last one.

    Caches are keyed by object IDs, so we can't clear them while they're being used by
    another thread."""

    def __enter__(self) -> None:
        global _scope_depth
        with _scope_lock:
            if _scope_depth == 0:
                # Make sure we start on a clean slate. Some tests may fail without this
                # due to memory address conflicts.
                clear_cache()
            _scope_depth += 1

    def __exit__(self, *_: Any) -> None:
        global _scope_depth
        with _scope_lock:
            _scope_depth -= 1
            if _scope_depth == 0:
                # Prevent unnecessary memory usage.
                clear_cache()


def make_cache() -> Dict[Any, Any]:
    """Make a dictionary that will be cleared at the start and end of each
    `tyro.cli()` call."""
    cache: Dict[Any, Any] = {}
    _cache_list.append(cache)
    return cache


# Objects whose IDs are used in cache keys. Holding references guarantees that IDs will
# not be reused before the caches are cleared.
_alive_from_id: Dict[int, Any] = make_cache()

_GenericAlias: Any = getattr(types, "GenericAlias", None)
_UnionType: Any = getattr(types, "UnionType", None)


def keep_alive(obj: Any) -> None:
    """Make sure an object isn't deallocated before the caches are cleared."""
    _alive_from_id[id(obj)] = obj


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
    if (cls is _GenericAlias or cls is _UnionType) and cls is not None:
        return (
            cls,
            getattr(typ, "__origin__", None),
            getattr(typ, "__unpacked__", False),
            tuple([type_key(arg) for arg in typ.__args__]),
        )
    obj_id = id(typ)
    _alive_from_id[obj_id] = typ
    return obj_id


def unsafe_cache(maxsize: int) -> Callable[[CallableType], CallableType]:
    """Cache decorator that relies object IDs when arguments are unhashable. Makes the
    very strong assumption of not only immutability, but that unhashable types don't go
    out of scope."""

    local_cache = make_cache()

    def inner(f: CallableType) -> CallableType:
        @functools.wraps(f)
        def wrapped_f(*args, **kwargs):
            key = tuple(_make_key(arg) for arg in args) + tuple(
                ("__kwarg__", k, _make_key(v)) for k, v in kwargs.items()
            )

            if key in local_cache:
                # Fuzzy check for cache collisions if called from a pytest test.
                if "pytest" in sys.modules:
                    import random

                    if random.random() < 0.1:
                        a = f(*args, **kwargs)
                        b = local_cache[key]
                        assert a == b or str(a) == str(b)

                return local_cache[key]

            out = f(*args, **kwargs)
            local_cache[key] = out
            if len(local_cache) > maxsize:
                local_cache.pop(next(iter(local_cache)))
            return out

        return wrapped_f  # type: ignore

    return inner


def _make_key(obj: Any) -> Any:
    """Some context: https://github.com/brentyi/tyro/issues/214"""
    try:
        # If the object is hashable, we can use it as a key directly.
        hash(obj)
        return obj
    except TypeError:
        # If the object is not hashable, we'll use assume the type/id are unique...
        return type(obj), id(obj)
