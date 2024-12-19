import functools
import sys
from typing import Any, Callable, Dict, List, TypeVar

CallableType = TypeVar("CallableType", bound=Callable)


_cache_list: List[Dict[Any, Any]] = []


def clear_cache() -> None:
    for c in _cache_list:
        c.clear()


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

                    if random.random() < 0.5:
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
