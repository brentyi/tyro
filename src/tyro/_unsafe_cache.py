import functools
import sys
import weakref
from typing import Any, Callable, Dict, List, Tuple, TypeVar

CallableType = TypeVar("CallableType", bound=Callable)


_cache_list: List[Dict[Any, Any]] = []
_object_id_counter = 0  # Global counter for unhashable objects.
_object_registry: Dict[
    int, Tuple[weakref.ref, int]
] = {}  # Maps Python IDs to (weakref, unique_id).


def clear_cache() -> None:
    for c in _cache_list:
        c.clear()
    # Don't reset the counter - it should only ever increase to ensure uniqueness.
    _object_registry.clear()


def unsafe_cache(maxsize: int) -> Callable[[CallableType], CallableType]:
    """Cache decorator that relies object IDs when arguments are unhashable. Makes the
    very strong assumption of not only immutability, but that unhashable types don't go
    out of scope."""

    _cache_list.append({})
    local_cache = _cache_list[-1]

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
        # If the object is not hashable, assign it a unique ID that never gets reused.
        global _object_id_counter

        obj_python_id = id(obj)

        # Check if we've seen this exact object before.
        if obj_python_id in _object_registry:
            ref, unique_id = _object_registry[obj_python_id]
            if ref() is obj:
                # This is the same object we've seen before.
                return type(obj), unique_id
            # Old object was garbage collected, will be overwritten below.

        # This is a new unhashable object. Assign it a unique ID.
        unique_id = _object_id_counter
        _object_id_counter += 1

        # Track the object with a weakref to detect when it's garbage collected.
        try:
            ref = weakref.ref(obj)
            _object_registry[obj_python_id] = (ref, unique_id)
        except TypeError:
            # Some objects don't support weakrefs. Just use the unique ID without tracking.
            pass

        return type(obj), unique_id
