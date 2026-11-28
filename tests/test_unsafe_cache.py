from typing import List, Literal, Union

from tyro import _unsafe_cache


def test_type_key() -> None:
    assert _unsafe_cache.type_key(int) == _unsafe_cache.type_key(int)
    assert _unsafe_cache.type_key(int) != _unsafe_cache.type_key(str)
    assert _unsafe_cache.type_key(List[int]) == _unsafe_cache.type_key(List[int])

    # These can be equal to each other, but aren't interchangeable.
    assert _unsafe_cache.type_key(Union[int, str]) != _unsafe_cache.type_key(
        Union[str, int]
    )
    assert _unsafe_cache.type_key(Literal[1, 2]) != _unsafe_cache.type_key(
        Literal[2, 1]
    )


def test_id_key() -> None:
    a: List[int] = []
    b: List[int] = []
    assert {_unsafe_cache.id_key(a): 1}[_unsafe_cache.id_key(a)] == 1
    assert _unsafe_cache.id_key(a) != _unsafe_cache.id_key(b)
    assert _unsafe_cache.id_key(None) == _unsafe_cache.id_key(None)


def test_hashable_key() -> None:
    assert _unsafe_cache.hashable_key((1, 2)) == _unsafe_cache.hashable_key((1, 2))
    assert _unsafe_cache.hashable_key([1]) != _unsafe_cache.hashable_key([1])


def test_cache_scope() -> None:
    cache = _unsafe_cache.make_cache()
    cache[1] = 2
    with _unsafe_cache.cache_scope():
        assert len(cache) == 0
        cache[1] = 2
    assert len(cache) == 0
