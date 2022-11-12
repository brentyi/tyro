import dataclasses
from typing import Any, Callable, Generic, TypeVar, Union

import pytest
from helptext_utils import get_helptext
from typing_extensions import Annotated

import tyro


def test_omit_subcommand_prefix():
    @dataclasses.dataclass
    class DefaultInstanceHTTPServer:
        y: int = 0
        flag: bool = True

    @dataclasses.dataclass
    class DefaultInstanceSMTPServer:
        z: int = 0

    @dataclasses.dataclass
    class DefaultInstanceSubparser:
        x: int
        # bc: Union[DefaultInstanceHTTPServer, DefaultInstanceSMTPServer]
        bc: tyro.conf.OmitSubcommandPrefixes[
            Union[DefaultInstanceHTTPServer, DefaultInstanceSMTPServer]
        ]

    assert (
        tyro.cli(
            DefaultInstanceSubparser,
            args=[
                "--x",
                "1",
                "bc:default-instance-http-server",
                "--y",
                "5",
                "--no-flag",
            ],
        )
        == tyro.cli(
            DefaultInstanceSubparser,
            args=["--x", "1", "bc:default-instance-http-server", "--y", "5"],
            default=DefaultInstanceSubparser(
                x=1, bc=DefaultInstanceHTTPServer(y=3, flag=False)
            ),
        )
        == DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=5, flag=False))
    )
    assert (
        tyro.cli(
            DefaultInstanceSubparser,
            args=["--x", "1", "bc:default-instance-http-server", "--y", "8"],
        )
        == tyro.cli(
            DefaultInstanceSubparser,
            args=["--x", "1", "bc:default-instance-http-server", "--y", "8"],
            default=DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=7)),
        )
        == DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=8))
    )


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
        bc: tyro.conf.AvoidSubcommands[
            Union[DefaultInstanceHTTPServer, DefaultInstanceSMTPServer]
        ]

    assert (
        tyro.cli(
            DefaultInstanceSubparser,
            args=["--x", "1", "bc:default-instance-http-server", "--bc.y", "5"],
        )
        == tyro.cli(
            DefaultInstanceSubparser,
            args=["--x", "1", "--bc.y", "5"],
            default=DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=3)),
        )
        == DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=5))
    )
    assert (
        tyro.cli(
            DefaultInstanceSubparser,
            args=["--x", "1", "bc:default-instance-http-server", "--bc.y", "8"],
        )
        == tyro.cli(
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
        tyro.cli(
            DefaultInstanceSubparser,
            args=["--x", "1", "bc:default-instance-http-server", "--bc.y", "5"],
        )
        == tyro.cli(
            tyro.conf.AvoidSubcommands[DefaultInstanceSubparser],
            args=["--x", "1", "--bc.y", "5"],
            default=DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=3)),
        )
        == DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=5))
    )
    assert tyro.cli(
        DefaultInstanceSubparser,
        args=["bc:default-instance-smtp-server", "--bc.z", "3"],
        default=DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=5)),
    ) == DefaultInstanceSubparser(x=1, bc=DefaultInstanceSMTPServer(z=3))
    assert (
        tyro.cli(
            tyro.conf.AvoidSubcommands[DefaultInstanceSubparser],
            args=["--x", "1", "bc:default-instance-http-server", "--bc.y", "8"],
        )
        == tyro.cli(
            tyro.conf.AvoidSubcommands[DefaultInstanceSubparser],
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
            Annotated[A, tyro.conf.subcommand("command-a", default=A(7))],
            Annotated[B, tyro.conf.subcommand("command-b", default=B(9))],
        ]

    @dataclasses.dataclass
    class Nested1:
        nested2: Nested2

    @dataclasses.dataclass
    class Parent:
        nested1: Nested1

    assert tyro.cli(
        Parent,
        args="nested1.nested2.subcommand:command-a".split(" "),
    ) == Parent(Nested1(Nested2(A(7))))
    assert tyro.cli(
        Parent,
        args=(
            "nested1.nested2.subcommand:command-a --nested1.nested2.subcommand.a 3".split(
                " "
            )
        ),
    ) == Parent(Nested1(Nested2(A(3))))

    assert tyro.cli(
        Parent,
        args="nested1.nested2.subcommand:command-b".split(" "),
    ) == Parent(Nested1(Nested2(B(9))))
    assert tyro.cli(
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
                Annotated[A, tyro.conf.subcommand("command-a", default=A(7))],
                Annotated[B, tyro.conf.subcommand("command-b", default=B(9))],
            ]
        ]

    @dataclasses.dataclass
    class Parent:
        nested1: Nested1

    assert tyro.cli(
        Parent,
        args="nested1.nested2.subcommand:command-a".split(" "),
    ) == Parent(Nested1(Nested2(A(7))))
    assert tyro.cli(
        Parent,
        args=(
            "nested1.nested2.subcommand:command-a --nested1.nested2.subcommand.a 3".split(
                " "
            )
        ),
    ) == Parent(Nested1(Nested2(A(3))))

    assert tyro.cli(
        Parent,
        args="nested1.nested2.subcommand:command-b".split(" "),
    ) == Parent(Nested1(Nested2(B(9))))
    assert tyro.cli(
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
            Annotated[T, tyro.conf.subcommand("command-a", default=A(7))],
            Annotated[B, tyro.conf.subcommand("command-b", default=B(9))],
        ]

    @dataclasses.dataclass
    class Nested1:
        nested2: Nested2[A]

    @dataclasses.dataclass
    class Parent:
        nested1: Nested1

    assert tyro.cli(
        Parent,
        args="nested1.nested2.subcommand:command-a".split(" "),
    ) == Parent(Nested1(Nested2(A(7))))
    assert tyro.cli(
        Parent,
        args=(
            "nested1.nested2.subcommand:command-a --nested1.nested2.subcommand.a 3".split(
                " "
            )
        ),
    ) == Parent(Nested1(Nested2(A(3))))

    assert tyro.cli(
        Parent,
        args="nested1.nested2.subcommand:command-b".split(" "),
    ) == Parent(Nested1(Nested2(B(9))))
    assert tyro.cli(
        Parent,
        args=(
            "nested1.nested2.subcommand:command-b --nested1.nested2.subcommand.b 7".split(
                " "
            )
        ),
    ) == Parent(Nested1(Nested2(B(7))))


def test_subparser_in_nested_with_metadata_default_matching():
    @dataclasses.dataclass(frozen=True)
    class A:
        a: int

    @dataclasses.dataclass
    class B:
        b: int
        a: A = A(5)

    default_one = B(3)
    default_two = B(9)

    @dataclasses.dataclass
    class Nested:
        subcommand: Union[
            # Annotated[A, tyro.conf.subcommand("zero")],
            Annotated[B, tyro.conf.subcommand("one", default=default_one)],
            Annotated[B, tyro.conf.subcommand("two", default=default_two)],
            Annotated[B, tyro.conf.subcommand("three")],
        ]

    # Match by hash.
    def main_one(x: Nested = Nested(default_one)) -> None:
        pass

    assert "default: x.subcommand:one" in get_helptext(main_one)

    # Match by value.
    def main_two(x: Nested = Nested(B(9))) -> None:
        pass

    assert "default: x.subcommand:two" in get_helptext(main_two)

    # Match by type.
    def main_three(x: Nested = Nested(B(15))) -> None:
        pass

    assert "default: x.subcommand:three" in get_helptext(main_three)


def test_flag():
    """When boolean flags have no default value, they must be explicitly specified."""

    @dataclasses.dataclass
    class A:
        x: bool

    assert tyro.cli(
        A,
        args=["--x"],
        default=A(False),
    ) == A(True)

    assert tyro.cli(
        tyro.conf.FlagConversionOff[A],
        args=["--x", "True"],
        default=A(False),
    ) == A(True)


def test_fixed():
    """When boolean flags have no default value, they must be explicitly specified."""

    @dataclasses.dataclass
    class A:
        x: tyro.conf.Fixed[bool]

    assert tyro.cli(
        A,
        args=[],
        default=A(True),
    ) == A(True)

    with pytest.raises(SystemExit):
        assert tyro.cli(
            tyro.conf.FlagConversionOff[A],
            args=["--x", "True"],
            default=A(False),
        ) == A(True)


def test_fixed_recursive():
    """When boolean flags have no default value, they must be explicitly specified."""

    @dataclasses.dataclass
    class A:
        x: bool

    assert tyro.cli(
        A,
        args=["--x"],
        default=A(False),
    ) == A(True)

    with pytest.raises(SystemExit):
        assert tyro.cli(
            tyro.conf.Fixed[tyro.conf.FlagConversionOff[A]],
            args=["--x", "True"],
            default=A(False),
        ) == A(True)


def test_suppressed_group():
    """Reproduction of https://github.com/nerfstudio-project/nerfstudio/issues/882."""

    @dataclasses.dataclass
    class Inner:
        a: int
        b: int

    def main(
        value: int,
        inner: tyro.conf.Suppress[Inner] = Inner(1, 2),
    ) -> int:
        return value + inner.a + inner.b

    assert tyro.cli(main, args=["--value", "5"]) == 8


def test_fixed_group():
    """Inspired by https://github.com/nerfstudio-project/nerfstudio/issues/882."""

    @dataclasses.dataclass
    class Inner:
        a: int
        b: int

    def main(
        value: int,
        inner: tyro.conf.Fixed[Inner] = Inner(1, 2),
    ) -> int:
        return value + inner.a + inner.b

    assert tyro.cli(main, args=["--value", "5"]) == 8


def test_fixed_suppressed_group():
    """Reproduction of https://github.com/nerfstudio-project/nerfstudio/issues/882."""

    @dataclasses.dataclass
    class Inner:
        a: int
        b: int

    def main(
        value: int,
        inner: tyro.conf.Fixed[Inner] = Inner(1, 2),
    ) -> int:
        return value + inner.a + inner.b

    assert tyro.cli(main, args=["--value", "5"]) == 8


def test_suppressed():
    @dataclasses.dataclass
    class Struct:
        a: int = 5
        b: tyro.conf.Suppress[str] = "7"

    def main(x: Any = Struct()):
        pass

    helptext = get_helptext(main)
    assert "--x.a" in helptext
    assert "--x.b" not in helptext


def test_suppress_manual_fixed():
    @dataclasses.dataclass
    class Struct:
        a: int = 5
        b: tyro.conf.SuppressFixed[tyro.conf.Fixed[str]] = "7"

    def main(x: Any = Struct()):
        pass

    helptext = get_helptext(main)
    assert "--x.a" in helptext
    assert "--x.b" not in helptext


def test_suppress_auto_fixed():
    @dataclasses.dataclass
    class Struct:
        a: int = 5
        b: Callable = lambda x: 5

    def main(x: tyro.conf.SuppressFixed[Any] = Struct()):
        pass

    helptext = get_helptext(main)
    assert "--x.a" in helptext
    assert "--x.b" not in helptext


def test_argconf_help():
    @dataclasses.dataclass
    class Struct:
        a: Annotated[
            int, tyro.conf.arg(name="nice", help="Hello world", metavar="NUMBER")
        ] = 5
        b: tyro.conf.Suppress[str] = "7"

    def main(x: Any = Struct()) -> int:
        return x.a

    helptext = get_helptext(main)
    assert "Hello world" in helptext
    assert "INT" not in helptext
    assert "NUMBER" in helptext
    assert "--x.a" not in helptext
    assert "--x.nice" in helptext
    assert "--x.b" not in helptext

    assert tyro.cli(main, args=[]) == 5
    assert tyro.cli(main, args=["--x.nice", "3"]) == 3


def test_positional():
    def main(x: tyro.conf.Positional[int], y: int) -> int:
        return x + y

    assert tyro.cli(main, args="5 --y 3".split(" ")) == 8
    assert tyro.cli(main, args="--y 3 5".split(" ")) == 8


def test_positional_order_swap():
    def main(x: int, y: tyro.conf.Positional[int]) -> int:
        return x + y

    assert tyro.cli(main, args="5 --x 3".split(" ")) == 8
    assert tyro.cli(main, args="--x 3 5".split(" ")) == 8
