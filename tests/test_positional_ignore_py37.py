from typing import List, Optional, Tuple

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
        def __init__(self, a: int, hello_world: int, /, c: int):
            self.hello_world = hello_world

    def nest1(a: int, b: int, thing: A, /, c: int) -> A:
        return thing

    assert isinstance(dcargs.cli(nest1, args="0 1 2 3 --thing.c 4 --c 4".split(" ")), A)
    assert (
        dcargs.cli(nest1, args="0 1 2 3 --thing.c 4 --c 4".split(" ")).hello_world == 3
    )
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


def test_positional_with_underscores():
    """Hyphen replacement works a bit different for positional arguments."""

    def main(a_multi_word_input: int, /) -> int:
        return a_multi_word_input

    assert dcargs.cli(main, args=["5"]) == 5


def test_positional_booleans():
    """Make sure that flag behavior is disabled for positional booleans."""

    def main(
        flag1: bool,
        flag2: bool = True,
        flag3: bool = False,
        /,
    ) -> Tuple[bool, bool, bool]:
        return flag1, flag2, flag3

    assert dcargs.cli(main, args=["True"]) == (True, True, False)
    assert dcargs.cli(main, args=["True", "False"]) == (True, False, False)
    assert dcargs.cli(main, args=["False", "False", "True"]) == (False, False, True)

    with pytest.raises(SystemExit):
        dcargs.cli(main, args=["hmm"])
    with pytest.raises(SystemExit):
        dcargs.cli(main, args=["true"])
    with pytest.raises(SystemExit):
        dcargs.cli(main, args=["True", "false"])


def test_optional_list():
    def main(a: Optional[List[int]], /) -> Optional[List[int]]:
        return a

    assert dcargs.cli(main, args=["None"]) is None
    assert dcargs.cli(main, args=["1", "2"]) == [1, 2]
    with pytest.raises(SystemExit):
        dcargs.cli(main, args=[])
    with pytest.raises(SystemExit):
        dcargs.cli(main, args=["hm"])


def test_optional_list_with_default():
    def main(a: Optional[List[int]] = None, /) -> Optional[List[int]]:
        return a

    assert dcargs.cli(main, args=["None"]) is None
    assert dcargs.cli(main, args=["5", "5"]) == [5, 5]
    with pytest.raises(SystemExit):
        dcargs.cli(main, args=["None", "5"])


def test_positional_tuple():
    def main(x: Tuple[int, int], y: Tuple[str, str], /):
        return x, y

    assert dcargs.cli(main, args="1 2 3 4".split(" ")) == ((1, 2), ("3", "4"))
