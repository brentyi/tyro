from __future__ import annotations

from typing import Annotated, List, Optional, Tuple

import pytest
from helptext_utils import get_helptext_with_checks

import tyro


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

    assert tyro.cli(main, args="1 2 --z 3".split(" ")) == (1, 2, 3)
    with pytest.raises(SystemExit):
        assert tyro.cli(main, args="--x 1 --y 2 --z 3".split(" ")) == (1, 2, 3)


class A:
    def __init__(self, a: int, hello_world: int, /, c: int):
        self.hello_world = hello_world


def test_nested_positional():
    def nest1(a: int, b: int, thing: A, /, c: int) -> A:
        return thing

    assert isinstance(tyro.cli(nest1, args="0 1 2 3 4 --c 4".split(" ")), A)
    assert tyro.cli(nest1, args="0 1 2 3 4 --c 4".split(" ")).hello_world == 3
    with pytest.raises(SystemExit):
        tyro.cli(nest1, args="0 1 2 3 4 4 --c 4".split(" "))


class B:
    def __init__(self, a: int, b: int, /, c: int):
        pass


def test_nested_positional_alt():
    def nest2(a: int, b: int, /, thing: B, c: int):
        return thing

    assert isinstance(tyro.cli(nest2, args="0 1 2 3 --thing.c 4 --c 4".split(" ")), B)
    with pytest.raises(SystemExit):
        tyro.cli(nest2, args="0 1 2 3 4 --thing.c 4 --c 4".split(" "))


def test_positional_with_underscores():
    """Hyphen replacement works a bit different for positional arguments."""

    def main(a_multi_word_input: int, /) -> int:
        return a_multi_word_input

    assert tyro.cli(main, args=["5"]) == 5


def test_positional_booleans():
    """Make sure that flag behavior is disabled for positional booleans."""

    def main(
        flag1: bool,
        flag2: bool = True,
        flag3: bool = False,
        /,
    ) -> Tuple[bool, bool, bool]:
        return flag1, flag2, flag3

    assert tyro.cli(main, args=["True"]) == (True, True, False)
    assert tyro.cli(main, args=["True", "False"]) == (True, False, False)
    assert tyro.cli(main, args=["False", "False", "True"]) == (False, False, True)

    with pytest.raises(SystemExit):
        tyro.cli(main, args=["hmm"])
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["true"])
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["True", "false"])


def test_optional_list():
    def main(a: Optional[List[int]], /) -> Optional[List[int]]:
        return a

    assert tyro.cli(main, args=["None"]) is None
    assert tyro.cli(main, args=["1", "2"]) == [1, 2]
    assert tyro.cli(main, args=[]) == []
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["hm"])


def test_optional_list_with_default():
    def main(a: Optional[List[int]] = None, /) -> Optional[List[int]]:
        return a

    assert tyro.cli(main, args=["None"]) is None
    assert tyro.cli(main, args=["5", "5"]) == [5, 5]
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["None", "5"])


def test_positional_tuple():
    def main(x: Tuple[int, int], y: Tuple[str, str], /):
        return x, y

    assert tyro.cli(main, args="1 2 3 4".split(" ")) == ((1, 2), ("3", "4"))


def make_list_of_strings_with_minimum_length(args: List[str]) -> List[str]:
    if len(args) == 0:
        raise ValueError("Expected at least one string")
    return args


ListOfStringsWithMinimumLength = Annotated[
    List[str],
    tyro.constructors.PrimitiveConstructorSpec(
        nargs="*",
        metavar="STR [STR ...]",
        is_instance=lambda x: isinstance(x, list)
        and all(isinstance(i, str) for i in x),
        instance_from_str=make_list_of_strings_with_minimum_length,
        str_from_instance=lambda args: args,
    ),
]


def test_min_length_custom_constructor_positional() -> None:
    def main(
        field1: ListOfStringsWithMinimumLength, /, field2: int = 3
    ) -> ListOfStringsWithMinimumLength:
        del field2
        return field1

    with pytest.raises(SystemExit):
        tyro.cli(main, args=[])
    assert tyro.cli(main, args=["a", "b"]) == ["a", "b"]


TupleCustomConstructor = Annotated[
    Tuple[str, ...],
    tyro.constructors.PrimitiveConstructorSpec(
        nargs="*",
        metavar="A TUPLE METAVAR",
        is_instance=lambda x: isinstance(x, tuple)
        and all(isinstance(i, str) for i in x),
        instance_from_str=lambda args: tuple(args),
        str_from_instance=lambda args: list(args),
    ),
]


def test_tuple_custom_constructors_positional() -> None:
    def main(field1: TupleCustomConstructor, /, field2: int = 3) -> Tuple[str, ...]:
        del field2
        return field1

    assert tyro.cli(main, args=["a", "b"]) == ("a", "b")
    assert tyro.cli(main, args=["a"]) == ("a",)
    assert tyro.cli(main, args=[]) == ()
    assert "A TUPLE METAVAR" in get_helptext_with_checks(main)


TupleCustomConstructor2 = Annotated[
    Tuple[str, ...],
    tyro.constructors.PrimitiveConstructorSpec(
        nargs="*",
        metavar="A TUPLE METAVAR",
        is_instance=lambda x: isinstance(x, tuple)
        and all(isinstance(i, str) for i in x),
        instance_from_str=lambda args: tuple(args),
        str_from_instance=lambda args: list(args),
    ),
]


def test_tuple_custom_constructors_positional_default_none() -> None:
    def main(
        field1: TupleCustomConstructor2 | None = None, /, field2: int = 3
    ) -> Tuple[str, ...] | None:
        del field2
        return field1

    assert tyro.cli(main, args=["a", "b"]) == ("a", "b")
    assert tyro.cli(main, args=["a"]) == ("a",)
    assert tyro.cli(main, args=[]) is None
    assert "A TUPLE METAVAR" in get_helptext_with_checks(main)


def test_tuple_custom_constructors_positional_default_five() -> None:
    def main(
        field1: TupleCustomConstructor2 | int = 5, /, field2: int = 3
    ) -> Tuple[str, ...] | int:
        del field2
        return field1

    assert tyro.cli(main, args=["a", "b"]) == ("a", "b")
    assert tyro.cli(main, args=["a"]) == ("a",)
    assert tyro.cli(main, args=[]) == 5
    assert "A TUPLE METAVAR" in get_helptext_with_checks(main)
