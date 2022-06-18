from typing import List, Tuple

import pytest

import dcargs


def test_positional():
    def main(
        x: int,
        y: int,
        /,
        # Note: it's generally a bad idea to have a mutable object (like a list) as a
        # default value. But it should still work.
        z: List[int] = [1, 2, 3],
    ) -> Tuple[int, int, int]:
        """main.

        Args:
            x: x
            y: y
            z: z

        Returns:
            Tuple[int, int, int]: Output.
        """
        return (x, y, z[0])

    assert dcargs.cli(main, args="1 2 --z 3".split(" ")) == (1, 2, 3)
    with pytest.raises(SystemExit):
        assert dcargs.cli(main, args="--x 1 --y 2 --z 3".split(" ")) == (1, 2, 3)


def test_nested_positional():
    class A:
        def __init__(self, a: int, b: int, /, c: int):
            pass

    def nest1(a: int, b: int, thing: A, /, c: int):
        return thing

    assert isinstance(dcargs.cli(nest1, args="0 1 2 3 --thing.c 4 --c 4".split(" ")), A)
    with pytest.raises(SystemExit):
        dcargs.cli(nest1, args="0 1 2 3 4 --thing.c 4 --c 4".split(" "))


def test_nested_positional_alt():
    class B:
        def __init__(self, a: int, b: int, /, c: int):
            pass

    def nest2(a: int, b: int, /, thing: B, c: int):
        return thing

    assert isinstance(dcargs.cli(nest2, args="0 1 2 3 --thing.c 4 --c 4".split(" ")), B)
    with pytest.raises(SystemExit):
        dcargs.cli(nest2, args="0 1 2 3 4 --thing.c 4 --c 4".split(" "))
