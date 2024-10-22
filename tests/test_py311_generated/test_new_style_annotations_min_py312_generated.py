# mypy: ignore-errors
#
# PEP 695 isn't yet supported in mypy. (April 4, 2024)
from dataclasses import dataclass
from typing import Annotated

import pytest

import tyro
from tyro.conf._markers import OmitArgPrefixes


def test_simple_generic():
    @dataclass(frozen=True)
    class Container[T]:
        a: T
        b: T

    assert tyro.cli(Container[int], args="--a 1 --b 2".split(" ")) == Container(1, 2)


type X = int
type Y = list[int]
type Z = Inner[int]


@dataclass(frozen=True)
class Inner[T]:
    a: T
    b: T


def test_generic_with_type_statement_0():
    @dataclass(frozen=True)
    class Container[T]:
        a: T
        b: T

    assert tyro.cli(Container[X], args="--a 1 --b 2".split(" ")) == Container(1, 2)


def test_generic_with_type_statement_1():
    @dataclass(frozen=True)
    class Container[T]:
        a: tuple[X, ...]
        b: T

    assert tyro.cli(Container[Y], args="--a 1 --b 2".split(" ")) == Container((1,), [2])


def test_generic_with_type_statement_2():
    @dataclass(frozen=True)
    class Container[T]:
        a: Z

    assert tyro.cli(Container[Y], args="--a.a 1 --a.b 2".split(" ")) == Container(
        Inner(1, 2)
    )


type AnnotatedBasic = Annotated[int, tyro.conf.arg(name="basic")]


def test_annotated_alias():
    @dataclass(frozen=True)
    class Container:
        a: AnnotatedBasic

    assert tyro.cli(Container, args="--basic 1".split(" ")) == Container(1)


type TT[T] = Annotated[T, tyro.conf.arg(name="", constructor=lambda: True)]


def test_pep695_generic_alias() -> None:
    """Adapted from: https://github.com/brentyi/tyro/issues/177"""

    @dataclass(frozen=True)
    class Config:
        arg: TT[bool]

    assert tyro.cli(Config, args=[]) == Config(arg=True)


type Renamed[T] = Annotated[T, tyro.conf.arg(name="renamed")]


def test_pep695_generic_alias_rename() -> None:
    """Adapted from: https://github.com/brentyi/tyro/issues/177"""

    @dataclass(frozen=True)
    class Config:
        arg: Renamed[bool]

    assert tyro.cli(Config, args=["--renamed", "True"]) == Config(arg=True)


def test_pep695_generic_alias_rename_override() -> None:
    """Adapted from: https://github.com/brentyi/tyro/issues/177"""

    @dataclass(frozen=True)
    class Config:
        arg: Annotated[Renamed[bool], tyro.conf.arg(name="renamed2")]

    assert tyro.cli(Config, args=["--renamed2", "True"]) == Config(arg=True)


type RenamedTwice[T] = Renamed[Renamed[T]]


def test_pep695_generic_alias_rename_twice() -> None:
    """Adapted from: https://github.com/brentyi/tyro/issues/177"""

    @dataclass(frozen=True)
    class Config:
        arg: RenamedTwice[bool]

    assert tyro.cli(Config, args=["--renamed", "True"]) == Config(arg=True)


type SomeUnion = bool | int
type RenamedThreeTimes[T] = Renamed[Renamed[Renamed[T]]]
type SomeUnionRenamed = RenamedThreeTimes[SomeUnion]


def test_pep695_generic_alias_rename_three_times() -> None:
    """Adapted from: https://github.com/brentyi/tyro/issues/177"""

    @dataclass(frozen=True)
    class Config:
        arg: Annotated[SomeUnionRenamed, tyro.conf.arg(name="renamed_override")]

    assert tyro.cli(Config, args=["--renamed-override", "True"]) == Config(arg=True)


type RecursiveList[T] = T | list[RecursiveList[T]]


def test_pep695_recursive_types() -> None:
    """Adapted from: https://github.com/brentyi/tyro/issues/177"""

    @dataclass(frozen=True)
    class Config:
        arg: RecursiveList[str]

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(Config, args=["--arg", "True"])


def test_pep695_recursive_types_custom_constructor() -> None:
    """Adapted from: https://github.com/brentyi/tyro/issues/177"""

    @dataclass(frozen=True)
    class Config:
        arg: Annotated[RecursiveList[str], tyro.conf.arg(constructor=str)]

    assert tyro.cli(Config, args=["--arg", "True"]) == Config(arg="True")


type UnprefixedSubcommandPair[T1, T2, T3] = (
    Annotated[OmitArgPrefixes[T1], tyro.conf.subcommand(prefix_name=False)]  # type: ignore
    | Annotated[T2, tyro.conf.subcommand(prefix_name=False)]  # type: ignore
    | Annotated[T3, tyro.conf.subcommand(prefix_name=True)]
)
type IntContainer = Inner[int]
type IntContainer2 = Inner[int]
type StrContainer = Inner[str]


def test_pep695_alias_subcommand() -> None:
    """Adapted from: https://github.com/brentyi/tyro/issues/177"""

    @dataclass(frozen=True)
    class Config:
        arg: UnprefixedSubcommandPair[IntContainer, IntContainer2, StrContainer]

    assert tyro.cli(Config, args=["int-container", "--a", "3", "--b", "5"]) == Config(
        Inner(3, 5)
    )
    assert tyro.cli(
        Config, args=["int-container2", "--arg.a", "3", "--arg.b", "5"]
    ) == Config(Inner(3, 5))
    assert tyro.cli(
        Config, args=["arg:str-container", "--arg.a", "3", "--arg.b", "5"]
    ) == Config(Inner("3", "5"))
