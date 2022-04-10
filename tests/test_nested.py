import dataclasses
from typing import Optional, Union

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

    assert (
        Nested(x=1, b=B(y=3))
        == dcargs.parse(Nested, args=["--x", "1", "--b.y", "3"])
        == dcargs.parse(Nested, args=[], default_instance=Nested(x=1, b=B(y=3)))
    )
    assert dcargs.parse(Nested, args=["--x", "1"]) == Nested(x=1, b=B(y=3))


def test_default_nested():
    @dataclasses.dataclass(frozen=True)
    class B:
        y: int = 3

    @dataclasses.dataclass(frozen=True)
    class Nested:
        x: int
        b: B = B(y=5)

    assert dcargs.parse(Nested, args=["--x", "1", "--b.y", "3"]) == Nested(
        x=1, b=B(y=3)
    )
    assert dcargs.parse(Nested, args=["--x", "1"]) == Nested(x=1, b=B(y=5))


def test_double_default_nested():
    @dataclasses.dataclass(frozen=True)
    class Child:
        y: int

    @dataclasses.dataclass(frozen=True)
    class Parent:
        c: Child

    @dataclasses.dataclass(frozen=True)
    class Grandparent:
        x: int
        b: Parent = Parent(Child(y=5))

    assert dcargs.parse(Grandparent, args=["--x", "1", "--b.c.y", "3"]) == Grandparent(
        x=1, b=Parent(Child(y=3))
    )
    assert dcargs.parse(Grandparent, args=["--x", "1"]) == Grandparent(
        x=1, b=Parent(Child(y=5))
    )


def test_default_factory_nested():
    @dataclasses.dataclass
    class B:
        y: int = 3

    @dataclasses.dataclass
    class Nested:
        x: int
        b: B = dataclasses.field(default_factory=lambda: B(y=5))

    assert dcargs.parse(Nested, args=["--x", "1", "--b.y", "3"]) == Nested(
        x=1, b=B(y=3)
    )
    assert dcargs.parse(Nested, args=["--x", "1"]) == Nested(x=1, b=B(y=5))


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


def test_subparser():
    @dataclasses.dataclass
    class HTTPServer:
        y: int

    @dataclasses.dataclass
    class SMTPServer:
        z: int

    @dataclasses.dataclass
    class Subparser:
        x: int
        bc: Union[HTTPServer, SMTPServer]

    assert dcargs.parse(
        Subparser, args=["--x", "1", "http-server", "--y", "3"]
    ) == Subparser(x=1, bc=HTTPServer(y=3))
    assert dcargs.parse(
        Subparser, args=["--x", "1", "smtp-server", "--z", "3"]
    ) == Subparser(x=1, bc=SMTPServer(z=3))

    with pytest.raises(SystemExit):
        # Missing subcommand.
        dcargs.parse(Subparser, args=["--x", "1"])
    with pytest.raises(SystemExit):
        # Wrong field.
        dcargs.parse(Subparser, args=["--x", "1", "http-server", "--z", "3"])
    with pytest.raises(SystemExit):
        # Wrong field.
        dcargs.parse(Subparser, args=["--x", "1", "smtp-server", "--y", "3"])


def test_subparser_with_default():
    @dataclasses.dataclass
    class DefaultHTTPServer:
        y: int

    @dataclasses.dataclass
    class DefaultSMTPServer:
        z: int

    @dataclasses.dataclass
    class DefaultSubparser:
        x: int
        bc: Union[DefaultHTTPServer, DefaultSMTPServer] = dataclasses.field(
            default_factory=lambda: DefaultHTTPServer(5)
        )

    assert (
        dcargs.parse(
            DefaultSubparser, args=["--x", "1", "default-http-server", "--y", "5"]
        )
        == dcargs.parse(DefaultSubparser, args=["--x", "1"])
        == DefaultSubparser(x=1, bc=DefaultHTTPServer(y=5))
    )
    assert dcargs.parse(
        DefaultSubparser, args=["--x", "1", "default-smtp-server", "--z", "3"]
    ) == DefaultSubparser(x=1, bc=DefaultSMTPServer(z=3))
    assert (
        dcargs.parse(
            DefaultSubparser, args=["--x", "1", "default-http-server", "--y", "8"]
        )
        == dcargs.parse(
            DefaultSubparser,
            args=[],
            default_instance=DefaultSubparser(x=1, bc=DefaultHTTPServer(y=8)),
        )
        == DefaultSubparser(x=1, bc=DefaultHTTPServer(y=8))
    )

    with pytest.raises(SystemExit):
        dcargs.parse(DefaultSubparser, args=["--x", "1", "b", "--z", "3"])
    with pytest.raises(SystemExit):
        dcargs.parse(DefaultSubparser, args=["--x", "1", "c", "--y", "3"])


def test_optional_subparser():
    @dataclasses.dataclass
    class OptionalHTTPServer:
        y: int

    @dataclasses.dataclass
    class OptionalSMTPServer:
        z: int

    @dataclasses.dataclass
    class OptionalSubparser:
        x: int
        bc: Optional[Union[OptionalHTTPServer, OptionalSMTPServer]]

    assert dcargs.parse(
        OptionalSubparser, args=["--x", "1", "optional-http-server", "--y", "3"]
    ) == OptionalSubparser(x=1, bc=OptionalHTTPServer(y=3))
    assert dcargs.parse(
        OptionalSubparser, args=["--x", "1", "optional-smtp-server", "--z", "3"]
    ) == OptionalSubparser(x=1, bc=OptionalSMTPServer(z=3))
    assert dcargs.parse(OptionalSubparser, args=["--x", "1"]) == OptionalSubparser(
        x=1, bc=None
    )

    with pytest.raises(SystemExit):
        # Wrong field.
        dcargs.parse(
            OptionalSubparser, args=["--x", "1", "optional-http-server", "--z", "3"]
        )
    with pytest.raises(SystemExit):
        # Wrong field.
        dcargs.parse(
            OptionalSubparser, args=["--x", "1", "optional-smtp-server", "--y", "3"]
        )
