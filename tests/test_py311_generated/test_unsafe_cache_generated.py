import gc

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


def test_unsafe_cache_id_reuse_bug():
    """Test that unsafe_cache correctly handles Python ID reuse after garbage collection."""

    # Clear any existing cache state from previous test runs.
    _unsafe_cache.clear_cache()

    # Create a cached function that returns different values for different unhashable objects.
    @_unsafe_cache.unsafe_cache(maxsize=100)
    def cached_func(obj):
        # Return a value based on the object's actual attributes.
        if hasattr(obj, "value"):
            return f"result_{obj.value}"
        return "no_value"

    # Create an unhashable class.
    class UnhashableClass:
        def __init__(self, value):
            self.value = value

        def __hash__(self):
            raise TypeError("unhashable type")

    # Try multiple times to trigger Python ID reuse.
    for attempt in range(10):
        # Step 1: Create first object and cache a result.
        obj1 = UnhashableClass(1)
        result1 = cached_func(obj1)
        assert result1 == "result_1"

        # Step 2: Store the ID of the first object.
        obj1_id = id(obj1)

        # Step 3: Delete the first object to free its ID.
        del obj1
        gc.collect()  # Force garbage collection.

        # Step 4: Create many new objects to increase chance of ID reuse.
        # In CPython, creating many objects increases the chance that one will reuse obj1's ID.
        for i in range(10000):
            new_obj = UnhashableClass(2)
            if id(new_obj) == obj1_id:
                # We found an object with the same ID!
                # Step 5: Call the cached function with the new object.
                # Without proper ID collision handling, this would incorrectly return
                # the cached result from obj1 ("result_1") instead of computing "result_2".
                result2 = cached_func(new_obj)

                # This assertion verifies the cache returns the correct result for the new object.
                assert result2 == "result_2", (
                    f"Cache collision detected! Got '{result2}' but expected 'result_2' (ID reuse after {i} iterations on attempt {attempt + 1})"
                )

                # Successfully verified cache handles ID reuse correctly.
                return

            # Keep references to prevent immediate reuse.
            if i % 100 != 0:
                del new_obj

    # If we couldn't reproduce ID reuse after all attempts, still pass.
    # The important thing is that when ID reuse happens, the cache handles it correctly.
    print(
        "Note: Could not reproduce ID reuse in this environment, but the cache should handle it correctly when it does occur."
    )
