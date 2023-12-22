import functools
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
            key = tuple(unsafe_hash(arg) for arg in args) + tuple(
                ("__kwarg__", k, unsafe_hash(v)) for k, v in kwargs.items()
            )

            if key in local_cache:
                return local_cache[key]

            out = f(*args, **kwargs)
            local_cache[key] = out
            if len(local_cache) > maxsize:
                local_cache.pop(next(iter(local_cache)))
            return out

        return wrapped_f  # type: ignore

    return inner


def unsafe_hash(obj: Any) -> Any:
    try:
        return hash(obj)
    except TypeError:
        return id(obj)
