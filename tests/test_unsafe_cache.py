from tyro import _unsafe_cache


def test_unsafe_cache():
    x = 0

    @_unsafe_cache.unsafe_cache(maxsize=2)
    def f(dummy: int):
        nonlocal x
        x += 1

    # >= is because of fuzz testing inside of unsafe_cache
    f(0)
    f(0)
    f(0)
    assert x >= 1
    f(1)
    f(1)
    f(1)
    assert x >= 2
    f(0)
    f(0)
    f(0)
    assert x >= 2
    f(2)
    f(2)
    f(2)
    assert x >= 3
    f(0)
    f(0)
    f(0)
    assert x >= 4
