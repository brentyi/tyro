import argparse
import contextlib
import dataclasses
import io
import json as json_
import shlex
from typing import Any, Dict, Generic, List, Sequence, Tuple, Type, TypeVar, Union

import pytest
from helptext_utils import get_helptext_with_checks
from typing_extensions import Annotated, TypedDict

import tyro


def test_suppress_subcommand() -> None:
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
        bc: tyro.conf.Suppress[
            Union[DefaultInstanceHTTPServer, DefaultInstanceSMTPServer]
        ] = dataclasses.field(default_factory=DefaultInstanceHTTPServer)

    assert "bc" not in get_helptext_with_checks(DefaultInstanceSubparser)


def test_omit_subcommand_prefix() -> None:
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
                "default-instance-http-server",
                "--y",
                "5",
                "--no-flag",
            ],
        )
        == tyro.cli(
            DefaultInstanceSubparser,
            args=["--x", "1", "default-instance-http-server", "--y", "5"],
            default=DefaultInstanceSubparser(
                x=1, bc=DefaultInstanceHTTPServer(y=3, flag=False)
            ),
        )
        == DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=5, flag=False))
    )
    assert (
        tyro.cli(
            DefaultInstanceSubparser,
            args=["--x", "1", "default-instance-http-server", "--y", "8"],
        )
        == tyro.cli(
            DefaultInstanceSubparser,
            args=["--x", "1", "default-instance-http-server", "--y", "8"],
            default=DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=7)),
        )
        == DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=8))
    )


def test_avoid_subparser_with_default() -> None:
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


def test_avoid_subparser_with_default_recursive() -> None:
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
        # Type ignore can be removed once TypeForm lands.
        # https://discuss.python.org/t/typeform-spelling-for-a-type-annotation-object-at-runtime/51435
        == tyro.cli(
            tyro.conf.AvoidSubcommands[DefaultInstanceSubparser],
            args=["--x", "1", "--bc.y", "5"],
            default=DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=3)),  # type: ignore
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
        # Type ignore can be removed once TypeForm lands.
        # https://discuss.python.org/t/typeform-spelling-for-a-type-annotation-object-at-runtime/51435
        == tyro.cli(
            tyro.conf.AvoidSubcommands[DefaultInstanceSubparser],
            args=["--bc.y", "8"],
            default=DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=7)),  # type: ignore
        )
        == DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=8))
    )


def test_subparser_in_nested_with_metadata() -> None:
    @dataclasses.dataclass(frozen=True)
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


def test_subparser_in_nested_with_metadata_suppressed() -> None:
    @dataclasses.dataclass(frozen=True)
    class A:
        a: tyro.conf.Suppress[int]

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

    # The `a` argument is suppresed.
    with pytest.raises(SystemExit):
        tyro.cli(
            Parent,
            args=(
                "nested1.nested2.subcommand:command-a --nested1.nested2.subcommand.a 3".split(
                    " "
                )
            ),
        )

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


def test_subparser_in_nested_with_metadata_generic() -> None:
    @dataclasses.dataclass(frozen=True)
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


def test_subparser_in_nested_with_metadata_generic_alt() -> None:
    @dataclasses.dataclass(frozen=True)
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


def test_subparser_in_nested_with_metadata_default_matching() -> None:
    @dataclasses.dataclass(frozen=True)
    class A:
        a: int

    @dataclasses.dataclass
    class B:
        b: int
        a: A = A(5)

    default_one = B(3)
    default_three = B(9)

    @dataclasses.dataclass
    class Nested:
        subcommand: Union[
            Annotated[B, tyro.conf.subcommand("one", default=default_one)],
            Annotated[B, tyro.conf.subcommand("two")],
            Annotated[B, tyro.conf.subcommand("three", default=default_three)],
        ]

    # Match by hash.
    def main_one(x: Nested = Nested(default_one)) -> None:
        pass

    assert "default: x.subcommand:one" in get_helptext_with_checks(main_one)

    # Match by value.
    def main_two(x: Nested = Nested(B(9))) -> None:
        pass

    assert "default: x.subcommand:three" in get_helptext_with_checks(main_two)

    # Match by type.
    def main_three(x: Nested = Nested(B(15))) -> None:
        pass

    assert "default: x.subcommand:one" in get_helptext_with_checks(main_three)


def test_flag() -> None:
    """When boolean flags have no default value, they must be explicitly specified."""

    @dataclasses.dataclass
    class A:
        x: bool

    assert tyro.cli(
        A,
        args=["--x"],
        default=A(False),
    ) == A(True)

    # Type ignore can be removed once TypeForm lands.
    # https://discuss.python.org/t/typeform-spelling-for-a-type-annotation-object-at-runtime/51435
    assert tyro.cli(
        tyro.conf.FlagConversionOff[A],
        args=["--x", "True"],
        default=A(False),  # type: ignore
    ) == A(True)
    assert tyro.cli(
        A,
        args=["--x", "True"],
        default=A(False),
        config=(tyro.conf.FlagConversionOff,),
    ) == A(True)


def test_fixed() -> None:
    """When an argument is fixed, we shouldn't be able to override it from the CLI."""

    @dataclasses.dataclass
    class A:
        x: tyro.conf.Fixed[bool]

    assert tyro.cli(
        A,
        args=[],
        default=A(True),
    ) == A(True)

    with pytest.raises(SystemExit):
        # Type ignore can be removed once TypeForm lands.
        # https://discuss.python.org/t/typeform-spelling-for-a-type-annotation-object-at-runtime/51435
        assert tyro.cli(
            tyro.conf.FlagConversionOff[A],
            args=["--x", "True"],
            default=A(False),  # type: ignore
        ) == A(True)

    with pytest.raises(SystemExit):
        assert tyro.cli(
            A,
            args=["--x", "True"],
            default=A(False),  # type: ignore
            config=(tyro.conf.FlagConversionOff,),
        ) == A(True)


def test_fixed_recursive() -> None:
    """When an argument is fixed, we shouldn't be able to override it from the CLI."""

    @dataclasses.dataclass
    class A:
        x: bool

    assert tyro.cli(
        A,
        args=["--x"],
        default=A(False),
    ) == A(True)

    # Type ignore can be removed once TypeForm lands.
    # https://discuss.python.org/t/typeform-spelling-for-a-type-annotation-object-at-runtime/51435
    with pytest.raises(SystemExit):
        assert tyro.cli(
            tyro.conf.Fixed[tyro.conf.FlagConversionOff[A]],
            args=["--x", "True"],
            default=A(False),  # type: ignore
        ) == A(True)


def test_type_with_no_conf_is_fixed() -> None:
    """The `type` type doesn't make sense to parse via the CLI, and should be
    fixed. See: https://github.com/brentyi/tyro/issues/164"""

    @dataclasses.dataclass
    class A:
        x: type = int

    assert tyro.cli(A, args=[]) == A()
    assert "fixed" in get_helptext_with_checks(A)


def test_suppressed_group() -> None:
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


def test_fixed_group() -> None:
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


def test_fixed_suppressed_group() -> None:
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


def test_suppressed() -> None:
    @dataclasses.dataclass
    class Struct:
        a: int = 5
        b: tyro.conf.Suppress[str] = "7"

    def main(x: Any = Struct()):
        pass

    helptext = get_helptext_with_checks(main)
    assert "--x.a" in helptext
    assert "--x.b" not in helptext


def test_suppress_manual_fixed() -> None:
    @dataclasses.dataclass
    class Struct:
        a: int = 5
        b: tyro.conf.SuppressFixed[tyro.conf.Fixed[str]] = "7"

    def main(x: Any = Struct()):
        pass

    helptext = get_helptext_with_checks(main)
    assert "--x.a" in helptext
    assert "--x.b" not in helptext


def test_suppress_manual_fixed_one_arg_only() -> None:
    @dataclasses.dataclass
    class Struct:
        b: tyro.conf.SuppressFixed[tyro.conf.Fixed[str]] = "7"

    def main(x: Any = Struct()):
        pass

    helptext = get_helptext_with_checks(main)
    assert "--x.a" not in helptext
    assert "--x.b" not in helptext


def test_suppress_auto_fixed() -> None:
    @dataclasses.dataclass
    class Struct:
        a: int = 5

        def b(self, x):
            return 5

    def main(x: tyro.conf.SuppressFixed[Any] = Struct()):
        pass

    helptext = get_helptext_with_checks(main)
    assert "--x.a" in helptext
    assert "--x.b" not in helptext


def test_argconf_help() -> None:
    @dataclasses.dataclass
    class Struct:
        a: Annotated[
            int,
            tyro.conf.arg(
                name="nice",
                help="Hello world",
                help_behavior_hint="(hint)",
                metavar="NUMBER",
            ),
        ] = 5
        b: tyro.conf.Suppress[str] = "7"

    def main(x: Any = Struct()) -> int:
        return x.a

    helptext = get_helptext_with_checks(main)
    assert "Hello world" in helptext
    assert "INT" not in helptext
    assert "NUMBER" in helptext
    assert "(hint)" in helptext
    assert "(default: 5)" not in helptext
    assert "--x.a" not in helptext
    assert "--x.nice" in helptext
    assert "--x.b" not in helptext

    assert tyro.cli(main, args=[]) == 5
    assert tyro.cli(main, args=["--x.nice", "3"]) == 3


def test_argconf_help_behavior_hint_lambda() -> None:
    @dataclasses.dataclass
    class Struct:
        a: Annotated[
            int,
            tyro.conf.arg(
                name="nice",
                help="Hello world",
                help_behavior_hint=lambda default: f"(default value: {default})",
                metavar="NUMBER",
            ),
        ] = 5
        b: tyro.conf.Suppress[str] = "7"

    def main(x: Any = Struct()) -> int:
        return x.a

    helptext = get_helptext_with_checks(main)
    assert "Hello world" in helptext
    assert "INT" not in helptext
    assert "NUMBER" in helptext
    assert "(default value: 5)" in helptext
    assert "(default: 5)" not in helptext
    assert "--x.a" not in helptext
    assert "--x.nice" in helptext
    assert "--x.b" not in helptext

    assert tyro.cli(main, args=[]) == 5
    assert tyro.cli(main, args=["--x.nice", "3"]) == 3


def test_argconf_no_prefix_help() -> None:
    @dataclasses.dataclass
    class Struct:
        a: Annotated[
            int,
            tyro.conf.arg(
                name="nice", help="Hello world", metavar="NUMBER", prefix_name=False
            ),
        ] = 5
        b: tyro.conf.Suppress[str] = "7"

    def main(x: Any = Struct()) -> int:
        return x.a

    helptext = get_helptext_with_checks(main)
    assert "Hello world" in helptext
    assert "INT" not in helptext
    assert "NUMBER" in helptext
    assert "--x.a" not in helptext
    assert "--x.nice" not in helptext
    assert "--nice" in helptext
    assert "--x.b" not in helptext

    assert tyro.cli(main, args=[]) == 5
    with pytest.raises(SystemExit):
        assert tyro.cli(main, args=["--x.nice", "3"]) == 3
    assert tyro.cli(main, args=["--nice", "3"]) == 3


def test_positional() -> None:
    def main(x: tyro.conf.Positional[int], y: int) -> int:
        return x + y

    assert tyro.cli(main, args="5 --y 3".split(" ")) == 8
    assert tyro.cli(main, args="--y 3 5".split(" ")) == 8


def test_positional_required_args() -> None:
    @dataclasses.dataclass
    class Args:
        x: int
        y: int = 3

    assert tyro.cli(
        tyro.conf.PositionalRequiredArgs[Args], args="5 --y 3".split(" ")
    ) == Args(5, 3)
    assert tyro.cli(
        tyro.conf.PositionalRequiredArgs[Args], args="--y 3 5".split(" ")
    ) == Args(5, 3)


def test_positional_order_swap() -> None:
    def main(x: int, y: tyro.conf.Positional[int]) -> int:
        return x + y

    assert tyro.cli(main, args="5 --x 3".split(" ")) == 8
    assert tyro.cli(main, args="--x 3 5".split(" ")) == 8


def test_omit_subcommand_prefix_and_consolidate_subcommand_args() -> None:
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
        ] = dataclasses.field(default_factory=DefaultInstanceHTTPServer)

    assert (
        tyro.cli(
            tyro.conf.ConsolidateSubcommandArgs[DefaultInstanceSubparser],
            args=[
                "default-instance-http-server",
                "--x",
                "1",
                "--y",
                "5",
                "--no-flag",
            ],
        )
        # Type ignore can be removed once TypeForm lands.
        # https://discuss.python.org/t/typeform-spelling-for-a-type-annotation-object-at-runtime/51435
        == tyro.cli(
            tyro.conf.ConsolidateSubcommandArgs[DefaultInstanceSubparser],
            args=[
                "default-instance-http-server",
                "--x",
                "1",
                "--y",
                "5",
            ],
            default=DefaultInstanceSubparser(  # type: ignore
                x=1, bc=DefaultInstanceHTTPServer(y=3, flag=False)
            ),
        )
        == DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=5, flag=False))
    )
    assert (
        tyro.cli(
            tyro.conf.ConsolidateSubcommandArgs[DefaultInstanceSubparser],
            args=[
                "default-instance-http-server",
                "--x",
                "1",
                "--y",
                "8",
            ],
        )
        # Type ignore can be removed once TypeForm lands.
        # https://discuss.python.org/t/typeform-spelling-for-a-type-annotation-object-at-runtime/51435
        == tyro.cli(
            tyro.conf.ConsolidateSubcommandArgs[DefaultInstanceSubparser],
            args=[
                "default-instance-http-server",
                "--x",
                "1",
                "--y",
                "8",
            ],
            default=DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=7)),  # type: ignore
        )
        == DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=8))
    )

    # Missing a default for --x.
    with pytest.raises(SystemExit):
        assert tyro.cli(
            tyro.conf.ConsolidateSubcommandArgs[DefaultInstanceSubparser], args=[]
        )


def test_omit_subcommand_prefix_and_consolidate_subcommand_args_in_function() -> None:
    @tyro.conf.configure(tyro.conf.subcommand(name="http-server"))
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
        bc: Union[DefaultInstanceHTTPServer, DefaultInstanceSMTPServer]

    @tyro.conf.configure(
        tyro.conf.OmitSubcommandPrefixes,
        tyro.conf.ConsolidateSubcommandArgs,
    )
    def func(parent: DefaultInstanceSubparser) -> DefaultInstanceSubparser:
        return parent

    assert tyro.cli(
        func,
        args=[
            "http-server",
            "--parent.x",
            "1",
            # --y and --no-flag are in a subcommand with prefix omission.
            "--y",
            "5",
            "--no-flag",
        ],
    ) == DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=5, flag=False))
    assert tyro.cli(
        func,
        args=[
            "http-server",
            "--parent.x",
            "1",
            # --y is in a subcommand with prefix omission.
            "--y",
            "8",
        ],
    ) == DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=8))


def test_append_lists() -> None:
    @dataclasses.dataclass
    class A:
        x: tyro.conf.UseAppendAction[List[int]]

    assert tyro.cli(A, args=[]) == A(x=[])
    assert tyro.cli(A, args="--x 1 --x 2 --x 3".split(" ")) == A(x=[1, 2, 3])
    assert tyro.cli(A, args=[]) == A(x=[])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x"])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "1", "2", "3"])


def test_append_sequence() -> None:
    @dataclasses.dataclass
    class A:
        x: tyro.conf.UseAppendAction[Sequence[int]]

    assert tyro.cli(A, args=[]) == A(x=[])
    assert tyro.cli(A, args="--x 1 --x 2 --x 3".split(" ")) == A(x=[1, 2, 3])
    assert tyro.cli(A, args=[]) == A(x=[])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x"])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "1", "2", "3"])


def test_append_tuple() -> None:
    @dataclasses.dataclass
    class A:
        x: tyro.conf.UseAppendAction[Tuple[int, ...]]

    assert tyro.cli(A, args=[]) == A(x=())
    assert tyro.cli(A, args="--x 1 --x 2 --x 3".split(" ")) == A(x=(1, 2, 3))
    assert tyro.cli(A, args=[]) == A(x=())
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x"])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "1", "2", "3"])


def test_append_tuple_with_default() -> None:
    @dataclasses.dataclass
    class A:
        x: tyro.conf.UseAppendAction[Tuple[int, ...]] = (1, 2)

    assert tyro.cli(A, args="--x 1 --x 2 --x 3".split(" ")) == A(x=(1, 2, 1, 2, 3))
    assert tyro.cli(A, args=[]) == A(x=(1, 2))
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x"])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "1", "2", "3"])


def test_append_nested_tuple_fixed_length() -> None:
    @dataclasses.dataclass
    class A:
        x: tyro.conf.UseAppendAction[Tuple[Tuple[str, int], ...]]

    assert tyro.cli(A, args="--x 1 1 --x 2 2 --x 3 3".split(" ")) == A(
        x=(("1", 1), ("2", 2), ("3", 3))
    )
    assert tyro.cli(A, args=[]) == A(x=())
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x"])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "1", "2", "3"])


def test_append_nested_tuple_with_default_fixed_length() -> None:
    @dataclasses.dataclass
    class A:
        x: tyro.conf.UseAppendAction[Tuple[Tuple[str, int], ...]] = (("1", 1), ("2", 2))

    assert tyro.cli(A, args="--x 1 1 --x 2 2 --x 3 3".split(" ")) == A(
        x=(("1", 1), ("2", 2), ("1", 1), ("2", 2), ("3", 3))
    )
    assert tyro.cli(A, args=[]) == A(x=(("1", 1), ("2", 2)))
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x"])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "1", "2", "3"])


def test_append_dict() -> None:
    @dataclasses.dataclass
    class A:
        x: tyro.conf.UseAppendAction[Dict[str, int]]

    assert tyro.cli(A, args="--x 1 1 --x 2 2 --x 3 3".split(" ")) == A(
        x={"1": 1, "2": 2, "3": 3}
    )
    assert tyro.cli(A, args=[]) == A(x={})
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x"])
    with pytest.raises(SystemExit):
        tyro.cli(A, args=["--x", "1", "2", "3"])


def test_append_dict_vague() -> None:
    @dataclasses.dataclass
    class A:
        x: tyro.conf.UseAppendAction[dict]

    assert tyro.cli(A, args="--x 1 1 --x 2 2 --x 3 3".split(" ")) == A(
        {"1": "1", "2": "2", "3": "3"}
    )


def test_append_dict_with_default() -> None:
    """Append has no impact when a dictionary has a default value."""

    @dataclasses.dataclass
    class A:
        x: tyro.conf.UseAppendAction[Dict[str, int]] = dataclasses.field(
            default_factory=lambda: {"1": 1}
        )

    assert tyro.cli(A, args=[]) == A(x={"1": 1})
    assert tyro.cli(A, args=["--x.1", "2"]) == A(x={"1": 2})
    with pytest.raises(SystemExit):
        assert tyro.cli(A, args="--x 2 2 --x 3 3".split(" ")) == A(
            x={"1": 1, "2": 2, "3": 3}
        )


def test_append_nested_tuple() -> None:
    @dataclasses.dataclass
    class A:
        x: tyro.conf.UseAppendAction[Tuple[Tuple[str, ...], ...]]

    assert tyro.cli(A, args="--x 1 2 3 --x 4 5".split(" ")) == A(
        x=(("1", "2", "3"), ("4", "5"))
    )
    assert tyro.cli(A, args=[]) == A(x=())


def test_append_nested_tuple_with_default() -> None:
    @dataclasses.dataclass
    class A:
        x: tyro.conf.UseAppendAction[Tuple[Tuple[str, ...], ...]] = (("1", "2"),)

    assert tyro.cli(A, args="--x 1 2 3 --x 4 5".split(" ")) == A(
        x=(("1", "2"), ("1", "2", "3"), ("4", "5"))
    )
    assert tyro.cli(A, args=[]) == A(x=(("1", "2"),))


def test_append_nested_list() -> None:
    @dataclasses.dataclass
    class A:
        x: tyro.conf.UseAppendAction[List[List[int]]]

    assert tyro.cli(A, args="--x 1 2 3 --x 4 5".split(" ")) == A(x=[[1, 2, 3], [4, 5]])
    assert tyro.cli(A, args=[]) == A(x=[])


def test_append_nested_dict() -> None:
    @dataclasses.dataclass
    class A:
        x: tyro.conf.UseAppendAction[List[Dict[str, int]]]

    assert tyro.cli(A, args="--x 1 2 3 4 --x 4 5".split(" ")) == A(
        x=[{"1": 2, "3": 4}, {"4": 5}]
    )
    assert tyro.cli(A, args=[]) == A(x=[])


def test_append_nested_dict_double() -> None:
    @dataclasses.dataclass
    class A:
        x: tyro.conf.UseAppendAction[Dict[str, Dict[str, int]]]

    assert tyro.cli(A, args="--x 0 1 2 3 4 --x 4 5 6".split(" ")) == A(
        x={"0": {"1": 2, "3": 4}, "4": {"5": 6}}
    )
    assert tyro.cli(A, args=[]) == A(x={})


def test_append_nested_dict_double_with_default() -> None:
    @dataclasses.dataclass
    class A:
        x: tyro.conf.UseAppendAction[Dict[str, Dict[str, int]]] = dataclasses.field(
            default_factory=dict
        )

    assert tyro.cli(A, args="--x 0 1 2 3 4 --x 4 5 6".split(" ")) == A(
        x={"0": {"1": 2, "3": 4}, "4": {"5": 6}}
    )
    assert tyro.cli(A, args=[]) == A(x={})


def test_duplicated_arg() -> None:
    # Loosely inspired by: https://github.com/brentyi/tyro/issues/49
    @dataclasses.dataclass
    class ModelConfig:
        num_slots: Annotated[int, tyro.conf.arg(prefix_name=False)]

    @dataclasses.dataclass
    class TrainConfig:
        num_slots: int
        model: ModelConfig

    with pytest.raises(argparse.ArgumentError):
        tyro.cli(TrainConfig, args="--num-slots 3".split(" "))


def test_omit_arg_prefixes() -> None:
    # Loosely inspired by: https://github.com/brentyi/tyro/issues/49
    @dataclasses.dataclass
    class ModelConfig:
        num_slots: int

    @dataclasses.dataclass
    class TrainConfig:
        model: ModelConfig

    assert tyro.cli(
        tyro.conf.OmitSubcommandPrefixes[TrainConfig],
        args="--model.num-slots 3".split(" "),
    ) == TrainConfig(ModelConfig(num_slots=3))

    annot = tyro.conf.OmitArgPrefixes[TrainConfig]
    assert tyro.cli(annot, args="--num-slots 3".split(" ")) == TrainConfig(
        ModelConfig(num_slots=3)
    )

    # Groups are still printed in the helptext.
    help_text = get_helptext_with_checks(annot)
    assert "model options" in help_text
    assert "--num-slots" in help_text


def test_custom_constructor_0() -> None:
    def times_two(n: str) -> int:
        return int(n) * 2

    @dataclasses.dataclass
    class Config:
        x: Annotated[int, tyro.conf.arg(name="x-renamed", constructor=times_two)]

    assert tyro.cli(Config, args="--x-renamed.n 5".split(" ")) == Config(x=10)


def test_custom_constructor_1() -> None:
    def times_two(n: int) -> int:
        return int(n) * 2

    @dataclasses.dataclass
    class Config:
        x: Annotated[int, tyro.conf.arg(constructor=times_two)]

    assert tyro.cli(Config, args="--x.n 5".split(" ")) == Config(x=10)


def test_custom_constructor_2() -> None:
    @dataclasses.dataclass
    class Config:
        x: Annotated[float, tyro.conf.arg(constructor=int)]

    assert tyro.cli(Config, args="--x 5".split(" ")) == Config(x=5)
    with pytest.raises(SystemExit):
        tyro.cli(Config, args="--x 5.23".split(" "))


def test_custom_constructor_3() -> None:
    def dict_from_json(json: str) -> dict:
        out = json_.loads(json)
        if not isinstance(out, dict):
            raise ValueError(f"{json} is not a dict!")
        return out

    @dataclasses.dataclass
    class Config:
        x: Annotated[
            dict,
            tyro.conf.arg(
                metavar="JSON",
                constructor=dict_from_json,
            ),
        ]

    assert tyro.cli(
        Config, args=shlex.split('--x.json \'{"hello": "world"}\'')
    ) == Config(x={"hello": "world"})

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stderr(target):
        tyro.cli(Config, args="--x.json 5".split(" "))

    error = target.getvalue()
    assert "Error parsing x: 5 is not a dict!" in error


def test_custom_constructor_4() -> None:
    @dataclasses.dataclass
    class Config:
        x: Annotated[float, tyro.conf.arg(constructor=int)] = 3.23

    assert tyro.cli(Config, args="--x 5".split(" ")) == Config(x=5)
    assert tyro.cli(Config, args=[]) == Config(x=3.23)


def test_custom_constructor_5() -> None:
    def make_float(a: float, b: float, c: float = 3) -> float:
        return a * b * c

    @dataclasses.dataclass
    class Config:
        x: Annotated[float, tyro.conf.arg(constructor=make_float)] = 3.23

    assert tyro.cli(Config, args=[]) == Config(x=3.23)
    assert tyro.cli(Config, args="--x.a 5 --x.b 2 --x.c 3".split(" ")) == Config(x=30)
    assert tyro.cli(Config, args="--x.a 5 --x.b 2".split(" ")) == Config(x=30)

    # --x.b is required!
    with pytest.raises(SystemExit):
        tyro.cli(Config, args="--x.a 5".split(" "))

    # --x.a and --x.b are required!
    with pytest.raises(SystemExit):
        tyro.cli(Config, args="--x.c 5".split(" "))


def test_custom_constructor_6() -> None:
    def make_float(
        a: tyro.conf.Positional[float],
        b2: Annotated[float, tyro.conf.arg(name="b")],
        c: float = 3,
    ) -> float:
        return a * b2 * c

    @dataclasses.dataclass
    class Config:
        x: Annotated[float, tyro.conf.arg(constructor=make_float)] = 3.23

    assert tyro.cli(Config, args=[]) == Config(x=3.23)
    assert tyro.cli(Config, args="--x.b 2 --x.c 3 5".split(" ")) == Config(x=30)
    assert tyro.cli(Config, args="--x.b 2 5".split(" ")) == Config(x=30)

    # --x.b is required!
    with pytest.raises(SystemExit):
        tyro.cli(Config, args="5".split(" "))

    # --x.a and --x.b are required!
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stderr(target):
        tyro.cli(Config, args="--x.c 5".split(" "))
    error = target.getvalue()
    assert "either all arguments must be provided" in error
    assert "or none of them" in error
    assert "We're missing arguments" in error


def test_custom_constructor_7() -> None:
    @dataclasses.dataclass
    class Struct:
        a: int
        b: int
        c: int = 3

    def make_float(struct: Struct) -> float:
        return struct.a * struct.b * struct.c

    @dataclasses.dataclass
    class Config:
        x: Annotated[float, tyro.conf.arg(constructor=make_float)] = 3.23

    assert tyro.cli(Config, args=[]) == Config(x=3.23)
    assert tyro.cli(
        Config, args="--x.struct.a 5 --x.struct.b 2 --x.struct.c 3".split(" ")
    ) == Config(x=30)
    assert tyro.cli(Config, args="--x.struct.a 5 --x.struct.b 2".split(" ")) == Config(
        x=30
    )

    # --x.struct.b is required!
    with pytest.raises(SystemExit):
        tyro.cli(Config, args="--x.struct.a 5".split(" "))

    # --x.struct.a and --x.struct.b are required!
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stderr(target):
        tyro.cli(Config, args="--x.struct.c 5".split(" "))
    error = target.getvalue()
    assert "We're missing arguments" in error
    assert "'--x.struct.b'" in error
    assert "'--x.struct.a'" in error  # The 5 is parsed into `a`.


def test_custom_constructor_8() -> None:
    @dataclasses.dataclass
    class Struct:
        a: tyro.conf.Positional[int]
        b: int
        c: int = 3

    def make_float(struct: Struct) -> float:
        return struct.a * struct.b * struct.c

    @dataclasses.dataclass
    class Config:
        x: Annotated[float, tyro.conf.arg(constructor=make_float)] = 3.23

    assert tyro.cli(Config, args=[]) == Config(x=3.23)
    assert tyro.cli(
        Config, args="--x.struct.b 2 --x.struct.c 3 5".split(" ")
    ) == Config(x=30)
    assert tyro.cli(Config, args="--x.struct.b 2 5".split(" ")) == Config(x=30)

    # --x.struct.b is required!
    with pytest.raises(SystemExit):
        tyro.cli(Config, args="5".split(" "))

    # --x.struct.a and --x.struct.b are required!
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stderr(target):
        tyro.cli(Config, args="--x.struct.b 5".split(" "))
    error = target.getvalue()
    assert "We're missing arguments" in error
    assert "'x.struct.a'" in error
    assert "'--x.struct.b'" not in error


def test_custom_constructor_9() -> None:
    def commit(branch: str) -> int:
        """Commit"""
        print(f"commit branch={branch}")
        return 3

    assert (
        tyro.cli(
            Annotated[Any, tyro.conf.arg(constructor=commit)],  # type: ignore
            args="--branch 5".split(" "),
        )
        == 3
    )


def test_custom_constructor_10() -> None:
    def commit(branch: str) -> int:
        """Commit"""
        print(f"commit branch={branch}")
        return 3

    def inner(x: Annotated[Any, tyro.conf.arg(constructor=commit)]) -> None:
        return x

    def inner_no_prefix(
        x: Annotated[Any, tyro.conf.arg(constructor=commit, prefix_name=False)],
    ) -> None:
        return x

    def outer(x: Annotated[Any, tyro.conf.arg(constructor=inner)]) -> None:
        return x

    def outer_no_prefix(
        x: Annotated[Any, tyro.conf.arg(constructor=inner_no_prefix)],
    ) -> None:
        return x

    assert (
        tyro.cli(
            outer,
            args="--x.x.branch 5".split(" "),
        )
        == 3
    )
    assert (
        tyro.cli(
            outer_no_prefix,
            args="--x.branch 5".split(" "),
        )
        == 3
    )


def test_alias() -> None:
    """Arguments with aliases."""

    @dataclasses.dataclass
    class Struct:
        a: Annotated[int, tyro.conf.arg(aliases=["--all", "-d"])]
        b: int
        c: int = 3

    def make_float(struct: Struct) -> float:
        return struct.a * struct.b * struct.c

    @dataclasses.dataclass
    class Config:
        x: Annotated[float, tyro.conf.arg(constructor=make_float)] = 3.23

    assert tyro.cli(Config, args=[]) == Config(x=3.23)
    assert tyro.cli(
        Config, args="--x.struct.b 2 --x.struct.c 3 --x.struct.a 5".split(" ")
    ) == Config(x=30)
    assert tyro.cli(
        Config, args="--x.struct.b 2 --x.struct.c 3 -d 5".split(" ")
    ) == Config(x=30)
    assert tyro.cli(
        Config, args="--x.struct.b 2 --x.struct.c 3 --all 5".split(" ")
    ) == Config(x=30)
    assert tyro.cli(Config, args="--x.struct.b 2 --x.struct.a 5".split(" ")) == Config(
        x=30
    )

    # --x.struct.b is required!
    with pytest.raises(SystemExit):
        tyro.cli(Config, args="--x.struct.a 5".split(" "))

    # --x.struct.a and --x.struct.b are required!
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stderr(target):
        tyro.cli(Config, args="--x.struct.b 5".split(" "))
    error = target.getvalue()
    assert "We're missing arguments" in error
    assert "'--all/-d/--x.struct.a'" in error
    assert "'--x.struct.b'" not in error

    assert "--all INT, -d INT, --x.struct.a INT" in get_helptext_with_checks(Config)


def test_positional_alias() -> None:
    """Positional arguments with aliases (which will be ignored)."""

    @dataclasses.dataclass
    class Struct:
        a: Annotated[tyro.conf.Positional[int], tyro.conf.arg(aliases=["--all", "-d"])]
        b: int
        c: int = 3

    def make_float(struct: Struct) -> float:
        return struct.a * struct.b * struct.c

    @dataclasses.dataclass
    class Config:
        x: Annotated[float, tyro.conf.arg(constructor=make_float)] = 3.23

    with pytest.warns(UserWarning):
        assert tyro.cli(Config, args=[]) == Config(x=3.23)
    with pytest.warns(UserWarning):
        assert tyro.cli(
            Config, args="--x.struct.b 2 --x.struct.c 3 5".split(" ")
        ) == Config(x=30)

    with pytest.raises(SystemExit), pytest.warns(UserWarning):
        assert tyro.cli(
            Config, args="--x.struct.b 2 --x.struct.c 3 -d 5".split(" ")
        ) == Config(x=30)
    with pytest.raises(SystemExit), pytest.warns(UserWarning):
        assert tyro.cli(
            Config, args="--x.struct.b 2 --x.struct.c 3 --all 5".split(" ")
        ) == Config(x=30)


def test_flag_alias() -> None:
    @dataclasses.dataclass
    class Struct:
        flag: Annotated[bool, tyro.conf.arg(aliases=["-f", "--flg"])] = False

    assert tyro.cli(Struct, args=[]).flag is False
    assert tyro.cli(Struct, args="--flag".split(" ")).flag is True
    assert tyro.cli(Struct, args="--no-flag".split(" ")).flag is False
    assert tyro.cli(Struct, args="--flg".split(" ")).flag is True
    assert tyro.cli(Struct, args="--no-flg".split(" ")).flag is False
    assert tyro.cli(Struct, args="-f".split(" ")).flag is True

    # BooleanOptionalAction will ignore arguments that aren't prefixed with --.
    with pytest.raises(SystemExit):
        tyro.cli(Struct, args="-no-f".split(" "))


def test_subcommand_constructor_mix() -> None:
    """https://github.com/brentyi/tyro/issues/89"""

    def checkout(branch: str) -> str:
        """Check out a branch."""
        return branch

    def commit(message: str, all: bool = False) -> str:
        """Make a commit."""
        return f"{message} {all}"

    @dataclasses.dataclass
    class Arg:
        foo: int = 1

    t: Any = Annotated[
        Union[
            Annotated[
                Any,
                tyro.conf.subcommand(name="checkout-renamed", constructor=checkout),
            ],
            Annotated[
                Any,
                tyro.conf.subcommand(name="commit", constructor=commit),
                tyro.conf.FlagConversionOff,
            ],
            Arg,
        ],
        tyro.conf.OmitArgPrefixes,  # Should do nothing.
    ]

    assert tyro.cli(t, args=["arg"]) == Arg()
    assert tyro.cli(t, args=["checkout-renamed", "--branch", "main"]) == "main"
    assert tyro.cli(t, args=["commit", "--message", "hi", "--all", "True"]) == "hi True"


def test_merge() -> None:
    """Test effect of tyro.conf.arg() on nested structures by approximating an
    HfArgumentParser-style API."""

    T = TypeVar("T")

    # We could add a lot overloads here if we were doing this for real. :)
    def instantiate_dataclasses(
        classes: Tuple[Type[T], ...], args: List[str]
    ) -> Tuple[T, ...]:
        return tyro.cli(
            tyro.conf.OmitArgPrefixes[  # type: ignore
                # Convert (type1, type2) into Tuple[type1, type2]
                Tuple[  # type: ignore
                    tuple(Annotated[c, tyro.conf.arg(name=c.__name__)] for c in classes)
                ]
            ],
            args=args,
        )

    @dataclasses.dataclass(frozen=True)
    class OptimizerConfig:
        lr: float = 1e-4
        weight: int = 10

    @dataclasses.dataclass(frozen=True)
    class DatasetConfig:
        batch_size: int = 1
        shuffle: bool = False

    assert instantiate_dataclasses(
        (OptimizerConfig, DatasetConfig), args=["--lr", "1e-3"]
    ) == (
        OptimizerConfig(1e-3),
        DatasetConfig(),
    )
    assert instantiate_dataclasses(
        (OptimizerConfig, DatasetConfig), args=["--lr", "1e-3", "--shuffle"]
    ) == (
        OptimizerConfig(1e-3),
        DatasetConfig(shuffle=True),
    )
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        instantiate_dataclasses((OptimizerConfig, DatasetConfig), args=["--help"])
    helptext = target.getvalue()
    assert "OptimizerConfig options" in helptext
    assert "DatasetConfig options" in helptext


def test_counter_action() -> None:
    def main(
        verbosity: tyro.conf.UseCounterAction[int],
        aliased_verbosity: Annotated[
            tyro.conf.UseCounterAction[int], tyro.conf.arg(aliases=["-v"])
        ],
    ) -> Tuple[int, int]:
        """Example showing how to use counter actions.
        Args:
            verbosity: Verbosity level.
            aliased_verbosity: Same as above, but can also be specified with -v, -vv, -vvv, etc.
        """
        return verbosity, aliased_verbosity

    assert tyro.cli(main, args=[]) == (0, 0)
    assert tyro.cli(main, args="--verbosity --verbosity".split(" ")) == (2, 0)
    assert tyro.cli(main, args="--verbosity --verbosity -v".split(" ")) == (2, 1)
    # Using shorthand combined flags (-vv, -vvv)
    assert tyro.cli(main, args="--verbosity --verbosity -vv".split(" ")) == (2, 2)
    assert tyro.cli(main, args="--verbosity --verbosity -vvv".split(" ")) == (2, 3)


def test_nested_suppress() -> None:
    @dataclasses.dataclass
    class Bconfig:
        b: int = 1

    @dataclasses.dataclass
    class Aconfig:
        a: str = "hello"
        b_conf: Bconfig = dataclasses.field(default_factory=Bconfig)

    assert tyro.cli(Aconfig, config=(tyro.conf.Suppress,), args=[]) == Aconfig()


def test_suppressed_subcommand() -> None:
    class Person(TypedDict):
        name: str
        age: int

    @dataclasses.dataclass
    class Train:
        person: tyro.conf.Suppress[Union[Person, None]] = None

    assert tyro.cli(Train, args=[]) == Train(None)


def test_avoid_subcommands_with_generics() -> None:
    T = TypeVar("T")

    @dataclasses.dataclass(frozen=True)
    class Person(Generic[T]):
        field: Union[T, bool]

    @dataclasses.dataclass
    class Train:
        person: Union[Person[int], Person[bool], Person[str], Person[float]] = Person(
            "hello"
        )

    assert tyro.cli(Train, config=(tyro.conf.AvoidSubcommands,), args=[]) == Train(
        person=Person("hello")
    )

    # No subcommand should be created.
    assert "STR|{True,False}" in get_helptext_with_checks(
        tyro.conf.AvoidSubcommands[Train]
    )
    assert "person:person-str" not in get_helptext_with_checks(
        tyro.conf.AvoidSubcommands[Train]
    )

    # Subcommand should be created.
    assert "STR|{True,False}" not in get_helptext_with_checks(Train)
    assert "person:person-str" in get_helptext_with_checks(Train)


def test_consolidate_subcommand_args_optional() -> None:
    """Adapted from @mirceamironenco: https://github.com/brentyi/tyro/issues/221"""

    @dataclasses.dataclass(frozen=True)
    class OptimizerConfig:
        lr: float = 1e-1

    @dataclasses.dataclass(frozen=True)
    class AdamConfig(OptimizerConfig):
        adam_foo: float = 1.0

    @dataclasses.dataclass(frozen=True)
    class SGDConfig(OptimizerConfig):
        sgd_foo: float = 1.0

    def _constructor() -> Type[OptimizerConfig]:
        cfgs = [
            Annotated[AdamConfig, tyro.conf.subcommand(name="adam")],
            Annotated[SGDConfig, tyro.conf.subcommand(name="sgd")],
        ]
        return Union.__getitem__(tuple(cfgs))  # type: ignore

    # Required because of --x.
    @dataclasses.dataclass
    class Config1:
        x: int
        optimizer: Annotated[
            Union[AdamConfig, SGDConfig],
            tyro.conf.arg(constructor_factory=_constructor),
        ] = AdamConfig()

    with pytest.raises(SystemExit):
        tyro.cli(Config1, config=(tyro.conf.ConsolidateSubcommandArgs,), args=[])

    # Required because of optimizer.
    @dataclasses.dataclass
    class Config2:
        optimizer: Annotated[
            Union[AdamConfig, SGDConfig],
            tyro.conf.arg(constructor_factory=_constructor),
        ]

    with pytest.raises(SystemExit):
        tyro.cli(Config2, config=(tyro.conf.ConsolidateSubcommandArgs,), args=[])

    # Optional!
    @dataclasses.dataclass
    class Config3:
        x: int = 3
        optimizer: Annotated[
            Union[AdamConfig, SGDConfig],
            tyro.conf.arg(constructor_factory=_constructor),
        ] = AdamConfig()

    assert (
        tyro.cli(Config3, config=(tyro.conf.ConsolidateSubcommandArgs,), args=[])
        == Config3()
    )


def test_consolidate_subcommand_args_optional_harder() -> None:
    """Adapted from @mirceamironenco: https://github.com/brentyi/tyro/issues/221"""

    @dataclasses.dataclass(frozen=True)
    class Leaf1:
        x: int = 5

    @dataclasses.dataclass(frozen=True)
    class Leaf2:
        x: int = 5

    @dataclasses.dataclass(frozen=True)
    class Branch1:
        x: int = 5
        leaf: Union[Leaf1, Leaf2] = Leaf2()

    @dataclasses.dataclass(frozen=True)
    class Branch2:
        x: int = 5
        leaf: Union[Leaf1, Leaf2] = Leaf2()

    @dataclasses.dataclass(frozen=True)
    class Trunk:
        branch: Union[Branch1, Branch2] = Branch2()

    assert (
        tyro.cli(Trunk, config=(tyro.conf.ConsolidateSubcommandArgs,), args=[])
        == Trunk()
    )

    with pytest.raises(SystemExit):
        tyro.cli(
            Trunk,
            default=Trunk(Branch2(leaf=Leaf1(x=tyro.MISSING))),
        )

    with pytest.raises(SystemExit):
        tyro.cli(Trunk, default=Trunk(Branch2(x=tyro.MISSING)), args=["branch:branch2"])

    assert tyro.cli(
        Trunk, default=Trunk(Branch2(x=tyro.MISSING)), args=["branch:branch1"]
    ) == Trunk(Branch1())


def test_default_subcommand_consistency() -> None:
    """https://github.com/brentyi/tyro/issues/221"""

    @dataclasses.dataclass(frozen=True)
    class OptimizerConfig:
        lr: float = 1e-1

    @dataclasses.dataclass(frozen=True)
    class AdamConfig(OptimizerConfig):
        adam_foo: float = 1.0

    @dataclasses.dataclass(frozen=True)
    class SGDConfig(OptimizerConfig):
        sgd_foo: float = 1.0

    def _constructor() -> Any:
        cfgs = [
            Annotated[SGDConfig, tyro.conf.subcommand(name="sgd", default=SGDConfig())],
            Annotated[
                AdamConfig, tyro.conf.subcommand(name="adam", default=AdamConfig())
            ],
        ]
        return Union.__getitem__(tuple(cfgs))  # type: ignore

    CLIOptimizer = Annotated[
        OptimizerConfig,
        tyro.conf.arg(constructor_factory=_constructor),
    ]

    @dataclasses.dataclass
    class Config:
        optimizer: CLIOptimizer = AdamConfig(adam_foo=0.5)  # type: ignore
        foo: int = 1
        bar: str = "abc"

    assert tyro.cli(Config, args=[]) == Config()
    assert (
        tyro.cli(
            Config,
            config=(tyro.conf.ConsolidateSubcommandArgs,),
            args=["optimizer:adam"],
        )
        == Config()
    )
    assert (
        tyro.cli(Config, config=(tyro.conf.ConsolidateSubcommandArgs,), args=[])
        == Config()
    )
    assert tyro.cli(Config, args=["optimizer:adam"]) == Config()


def test_suppress_in_union() -> None:
    @dataclasses.dataclass
    class ConfigA:
        x: int

    @dataclasses.dataclass
    class ConfigB:
        y: Union[int, Annotated[str, tyro.conf.Suppress]]
        z: Annotated[Union[str, int], tyro.conf.Suppress] = 3

    def main(
        x: Union[Annotated[ConfigA, tyro.conf.Suppress], ConfigB] = ConfigA(3),
    ) -> Any:
        return x

    assert tyro.cli(main, args="x:config-b --x.y 5".split(" ")) == ConfigB(5)

    with pytest.raises(SystemExit):
        # ConfigA is suppressed, so there'll be no default.
        tyro.cli(main, args=[])
    with pytest.raises(SystemExit):
        # ConfigB needs an int, since str is suppressed.
        tyro.cli(main, args="x:config-b --x.y five".split(" "))
    with pytest.raises(SystemExit):
        # The z argument is suppressed.
        tyro.cli(main, args="x:config-b --x.y 5 --x.z 3".split(" "))
    with pytest.raises(SystemExit):
        # ConfigA is suppressed.
        assert tyro.cli(main, args=["x:config-a"])
    with pytest.raises(SystemExit):
        # ConfigB has a required argument.
        assert tyro.cli(main, args=["x:config-b"])


_dataset_map = {
    "alpaca": "tatsu-lab/alpaca",
    "alpaca_clean": "yahma/alpaca-cleaned",
    "alpaca_gpt4": "vicgalle/alpaca-gpt4",
}
_inv_dataset_map = {value: key for key, value in _dataset_map.items()}
_datasets = list(_dataset_map.keys())

HFDataset = Annotated[
    str,
    tyro.constructors.PrimitiveConstructorSpec(
        nargs=1,
        metavar="{" + ",".join(_datasets) + "}",
        instance_from_str=lambda args: _dataset_map[args[0]],
        is_instance=lambda instance: isinstance(instance, str)
        and instance in _inv_dataset_map,
        str_from_instance=lambda instance: [_inv_dataset_map[instance]],
        choices=tuple(_datasets),
    ),
    tyro.conf.arg(
        help_behavior_hint=lambda df: f"(default: {df}, run datasets.py for full options)"
    ),
]


def test_annotated_attribute_inheritance() -> None:
    """From @mirceamironenco.

    https://github.com/brentyi/tyro/issues/239"""

    @dataclasses.dataclass(frozen=True)
    class TrainConfig:
        dataset: str = "vicgalle/alpaca-gpt4"

    @dataclasses.dataclass(frozen=True)
    class CLITrainerConfig(TrainConfig):
        dataset: HFDataset = "vicgalle/alpaca-gpt4"

    assert "{alpaca,alpaca_clean,alpaca_gpt4}" in get_helptext_with_checks(
        CLITrainerConfig
    )
    assert (
        "default: alpaca_gpt4, run datasets.py for full options"
        in get_helptext_with_checks(CLITrainerConfig)
    )


@dataclasses.dataclass(frozen=True)
class OptimizerConfig:
    lr: float = 1e-1


@dataclasses.dataclass(frozen=True)
class AdamConfig(OptimizerConfig):
    adam_foo: float = 1.0


@dataclasses.dataclass(frozen=True)
class SGDConfig(OptimizerConfig):
    sgd_foo: float = 1.0


@dataclasses.dataclass
class TrainConfig:
    optimizer: OptimizerConfig = AdamConfig()


def _dummy_constructor() -> Type[OptimizerConfig]:
    return Union[AdamConfig, SGDConfig]  # type: ignore


CLIOptimizerConfig = Annotated[
    OptimizerConfig,
    tyro.conf.arg(constructor_factory=_dummy_constructor),
]


def test_attribute_inheritance_2() -> None:
    """From @mirceamironenco.

    https://github.com/brentyi/tyro/issues/239"""

    @dataclasses.dataclass
    class CLITrainerConfig(TrainConfig):
        optimizer: CLIOptimizerConfig = SGDConfig()

    assert "[{optimizer:adam-config,optimizer:sgd-config}]" in get_helptext_with_checks(
        CLITrainerConfig
    )


@dataclasses.dataclass
class Config:
    # Comment in helptext.
    y: int = 0


def test_helptext_from_contents_off() -> None:
    assert "Comment in helptext." in get_helptext_with_checks(Config)
    assert "Comment in helptext." not in get_helptext_with_checks(
        tyro.conf.HelptextFromCommentsOff[Config]
    )
