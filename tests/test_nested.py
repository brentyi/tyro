import dataclasses

import pytest

import dcargs


def test_nested():
    @dataclasses.dataclass
    class B:
        y: int

    @dataclasses.dataclass
    class Nested:
        x: int
        b: B

    assert dcargs.parse(Nested, args=["--x", "1", "--b.y", "3"]) == Nested(
        x=1, b=B(y=3)
    )
    with pytest.raises(SystemExit):
        dcargs.parse(Nested, args=["--x", "1"])


def test_nested_default():
    @dataclasses.dataclass
    class B:
        y: int = 3

    @dataclasses.dataclass
    class Nested:
        x: int
        b: B

    assert dcargs.parse(Nested, args=["--x", "1", "--b.y", "3"]) == Nested(
        x=1, b=B(y=3)
    )
    assert dcargs.parse(Nested, args=["--x", "1"]) == Nested(x=1, b=B(y=3))


def test_default_nested():
    @dataclasses.dataclass
    class B:
        y: int = 3

    @dataclasses.dataclass
    class Nested:
        x: int
        b: B = B(y=5)

    assert dcargs.parse(Nested, args=["--x", "1", "--b.y", "3"]) == Nested(
        x=1, b=B(y=3)
    )
    assert dcargs.parse(Nested, args=["--x", "1"]) == Nested(x=1, b=B(y=5))


def test_double_default_nested():
    @dataclasses.dataclass
    class Child:
        y: int

    @dataclasses.dataclass
    class Parent:
        c: Child

    @dataclasses.dataclass
    class Grandparent:
        x: int
        b: Parent = Parent(Child(y=5))

    assert dcargs.parse(Grandparent, args=["--x", "1", "--b.c.y", "3"]) == Grandparent(
        x=1, b=Parent(Child(y=3))
    )
    assert dcargs.parse(Grandparent, args=["--x", "1"]) == Grandparent(
        x=1, b=Parent(Child(y=5))
    )


# TODO: implement this!
# def test_optional_nested():
#     @dataclasses.dataclass
#     class OptionalNestedChild:
#         y: int
#         z: int
#
#     @dataclasses.dataclass
#     class OptionalNested:
#         x: int
#         b: Optional[OptionalNestedChild]
#
#     assert dcargs.parse(OptionalNested, args=["--x", "1"]) == OptionalNested(
#         x=1, b=None
#     )
#     with pytest.raises(SystemExit):
#         dcargs.parse(OptionalNested, args=["--x", "1", "--b.y", "3"])
#     with pytest.raises(SystemExit):
#         dcargs.parse(OptionalNested, args=["--x", "1", "--b.z", "3"])
#
#     assert dcargs.parse(
#         OptionalNested, args=["--x", "1", "--b.y", "2", "--b.z", "3"]
#     ) == OptionalNested(x=1, b=OptionalNestedChild(y=2, z=3))
