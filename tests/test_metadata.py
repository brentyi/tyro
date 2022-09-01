import dataclasses
from typing import Generic, TypeVar, Union

import pytest
from typing_extensions import Annotated

import dcargs


def test_avoid_subparser_with_default():
    @dataclasses.dataclass
    class DefaultInstanceHTTPServer:
        y: int = 0

    @dataclasses.dataclass
    class DefaultInstanceSMTPServer:
        z: int = 0

    @dataclasses.dataclass
    class DefaultInstanceSubparser:
        x: int
        bc: dcargs.conf.AvoidSubcommands[
            Union[DefaultInstanceHTTPServer, DefaultInstanceSMTPServer]
        ]

    assert (
        dcargs.cli(
            DefaultInstanceSubparser,
            args=["--x", "1", "bc:default-instance-http-server", "--bc.y", "5"],
        )
        == dcargs.cli(
            DefaultInstanceSubparser,
            args=["--x", "1", "--bc.y", "5"],
            default=DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=3)),
        )
        == DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=5))
    )
    assert (
        dcargs.cli(
            DefaultInstanceSubparser,
            args=["--x", "1", "bc:default-instance-http-server", "--bc.y", "8"],
        )
        == dcargs.cli(
            DefaultInstanceSubparser,
            args=["--bc.y", "8"],
            default=DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=7)),
        )
        == DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=8))
    )


def test_avoid_subparser_with_default_recursive():
    @dataclasses.dataclass
    class DefaultInstanceHTTPServer:
        y: int = 0

    @dataclasses.dataclass
    class DefaultInstanceSMTPServer:
        z: int = 0

    @dataclasses.dataclass
    class DefaultInstanceSubparser:
        x: int
        bc: Union[DefaultInstanceHTTPServer, DefaultInstanceSMTPServer]

    assert (
        dcargs.cli(
            DefaultInstanceSubparser,
            args=["--x", "1", "bc:default-instance-http-server", "--bc.y", "5"],
        )
        == dcargs.cli(
            dcargs.conf.AvoidSubcommands[DefaultInstanceSubparser],
            args=["--x", "1", "--bc.y", "5"],
            default=DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=3)),
        )
        == DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=5))
    )
    assert dcargs.cli(
        DefaultInstanceSubparser,
        args=["bc:default-instance-smtp-server", "--bc.z", "3"],
        default=DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=5)),
    ) == DefaultInstanceSubparser(x=1, bc=DefaultInstanceSMTPServer(z=3))
    assert (
        dcargs.cli(
            dcargs.conf.AvoidSubcommands[DefaultInstanceSubparser],
            args=["--x", "1", "bc:default-instance-http-server", "--bc.y", "8"],
        )
        == dcargs.cli(
            dcargs.conf.AvoidSubcommands[DefaultInstanceSubparser],
            args=["--bc.y", "8"],
            default=DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=7)),
        )
        == DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=8))
    )


def test_subparser_in_nested_with_metadata():
    @dataclasses.dataclass
    class A:
        a: int

    @dataclasses.dataclass
    class B:
        b: int
        a: A = A(5)

    @dataclasses.dataclass
    class Nested2:
        subcommand: Union[
            Annotated[A, dcargs.conf.subcommand("command-a", default=A(7))],
            Annotated[B, dcargs.conf.subcommand("command-b", default=B(9))],
        ]

    @dataclasses.dataclass
    class Nested1:
        nested2: Nested2

    @dataclasses.dataclass
    class Parent:
        nested1: Nested1

    assert dcargs.cli(
        Parent,
        args="nested1.nested2.subcommand:command-a".split(" "),
    ) == Parent(Nested1(Nested2(A(7))))
    assert dcargs.cli(
        Parent,
        args=(
            "nested1.nested2.subcommand:command-a --nested1.nested2.subcommand.a 3".split(
                " "
            )
        ),
    ) == Parent(Nested1(Nested2(A(3))))

    assert dcargs.cli(
        Parent,
        args="nested1.nested2.subcommand:command-b".split(" "),
    ) == Parent(Nested1(Nested2(B(9))))
    assert dcargs.cli(
        Parent,
        args=(
            "nested1.nested2.subcommand:command-b --nested1.nested2.subcommand.b 7".split(
                " "
            )
        ),
    ) == Parent(Nested1(Nested2(B(7))))


def test_subparser_in_nested_with_metadata_generic():
    @dataclasses.dataclass
    class A:
        a: int

    @dataclasses.dataclass
    class B:
        b: int
        a: A = A(5)

    T = TypeVar("T")

    @dataclasses.dataclass
    class Nested2(Generic[T]):
        subcommand: T

    @dataclasses.dataclass
    class Nested1:
        nested2: Nested2[
            Union[
                Annotated[A, dcargs.conf.subcommand("command-a", default=A(7))],
                Annotated[B, dcargs.conf.subcommand("command-b", default=B(9))],
            ]
        ]

    @dataclasses.dataclass
    class Parent:
        nested1: Nested1

    assert dcargs.cli(
        Parent,
        args="nested1.nested2.subcommand:command-a".split(" "),
    ) == Parent(Nested1(Nested2(A(7))))
    assert dcargs.cli(
        Parent,
        args=(
            "nested1.nested2.subcommand:command-a --nested1.nested2.subcommand.a 3".split(
                " "
            )
        ),
    ) == Parent(Nested1(Nested2(A(3))))

    assert dcargs.cli(
        Parent,
        args="nested1.nested2.subcommand:command-b".split(" "),
    ) == Parent(Nested1(Nested2(B(9))))
    assert dcargs.cli(
        Parent,
        args=(
            "nested1.nested2.subcommand:command-b --nested1.nested2.subcommand.b 7".split(
                " "
            )
        ),
    ) == Parent(Nested1(Nested2(B(7))))


def test_subparser_in_nested_with_metadata_generic_alt():
    @dataclasses.dataclass
    class A:
        a: int

    @dataclasses.dataclass
    class B:
        b: int
        a: A = A(5)

    T = TypeVar("T")

    @dataclasses.dataclass
    class Nested2(Generic[T]):
        subcommand: Union[
            Annotated[T, dcargs.conf.subcommand("command-a", default=A(7))],
            Annotated[B, dcargs.conf.subcommand("command-b", default=B(9))],
        ]

    @dataclasses.dataclass
    class Nested1:
        nested2: Nested2[A]

    @dataclasses.dataclass
    class Parent:
        nested1: Nested1

    assert dcargs.cli(
        Parent,
        args="nested1.nested2.subcommand:command-a".split(" "),
    ) == Parent(Nested1(Nested2(A(7))))
    assert dcargs.cli(
        Parent,
        args=(
            "nested1.nested2.subcommand:command-a --nested1.nested2.subcommand.a 3".split(
                " "
            )
        ),
    ) == Parent(Nested1(Nested2(A(3))))

    assert dcargs.cli(
        Parent,
        args="nested1.nested2.subcommand:command-b".split(" "),
    ) == Parent(Nested1(Nested2(B(9))))
    assert dcargs.cli(
        Parent,
        args=(
            "nested1.nested2.subcommand:command-b --nested1.nested2.subcommand.b 7".split(
                " "
            )
        ),
    ) == Parent(Nested1(Nested2(B(7))))


def test_flag():
    """When boolean flags have no default value, they must be explicitly specified."""

    @dataclasses.dataclass
    class A:
        x: bool

    assert dcargs.cli(
        A,
        args=["--x"],
        default=A(False),
    ) == A(True)

    assert dcargs.cli(
        dcargs.conf.FlagConversionOff[A],
        args=["--x", "True"],
        default=A(False),
    ) == A(True)


def test_fixed():
    """When boolean flags have no default value, they must be explicitly specified."""

    @dataclasses.dataclass
    class A:
        x: dcargs.conf.Fixed[bool]

    assert dcargs.cli(
        A,
        args=[],
        default=A(True),
    ) == A(True)

    with pytest.raises(SystemExit):
        assert dcargs.cli(
            dcargs.conf.FlagConversionOff[A],
            args=["--x", "True"],
            default=A(False),
        ) == A(True)


def test_fixed_recursive():
    """When boolean flags have no default value, they must be explicitly specified."""

    @dataclasses.dataclass
    class A:
        x: bool

    assert dcargs.cli(
        A,
        args=["--x"],
        default=A(False),
    ) == A(True)

    with pytest.raises(SystemExit):
        assert dcargs.cli(
            dcargs.conf.Fixed[
                dcargs.conf.FlagConversionOff[A],
            ],
            args=["--x", "True"],
            default=A(False),
        ) == A(True)
