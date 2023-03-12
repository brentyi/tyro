import functools
from typing import Any, Callable, Dict, TypeVar

CallableType = TypeVar("CallableType", bound=Callable)


def unsafe_cache(maxsize: int) -> Callable[[CallableType], CallableType]:
    """Cache decorator that relies object IDs when arguments are unhashable. Assumes
    immutability."""
    cache: Dict[Any, Any] = {}

    def inner(f: CallableType) -> CallableType:
        @functools.wraps(f)
        def wrapped_f(*args, **kwargs):
            key = tuple(unsafe_hash(arg) for arg in args) + tuple(
                ("__kwarg__", k, unsafe_hash(v)) for k, v in kwargs.items()
            )

            if key in cache:
                return cache[key]

            out = f(*args, **kwargs)
            cache[key] = out
            if len(cache) > maxsize:
                cache.pop(next(iter(cache)))
            return out

        return wrapped_f  # type: ignore

    return inner


def unsafe_hash(obj: Any) -> Any:
    try:
        return hash(obj)
    except TypeError:
        return id(obj)
