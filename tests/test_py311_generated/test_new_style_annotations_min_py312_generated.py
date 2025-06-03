# mypy: ignore-errors
#
# PEP 695 isn't yet supported in mypy. (April 4, 2024)
from dataclasses import dataclass
from typing import Annotated, Any, Literal, NewType

import pytest
from helptext_utils import get_helptext_with_checks
from pydantic import BaseModel

import tyro
from tyro.conf._markers import OmitArgPrefixes
from tyro.constructors import UnsupportedTypeAnnotationError


def test_simple_generic() -> None:
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


def test_generic_with_type_statement_0() -> None:
    @dataclass(frozen=True)
    class Container[T]:
        a: T
        b: T

    assert tyro.cli(Container[X], args="--a 1 --b 2".split(" ")) == Container(1, 2)


def test_generic_with_type_statement_1() -> None:
    @dataclass(frozen=True)
    class Container[T]:
        a: tuple[X, ...]
        b: T

    assert tyro.cli(Container[Y], args="--a 1 --b 2".split(" ")) == Container((1,), [2])


def test_generic_with_type_statement_2() -> None:
    @dataclass(frozen=True)
    class Container[T]:
        a: Z

    assert tyro.cli(Container[Y], args="--a.a 1 --a.b 2".split(" ")) == Container(
        Inner(1, 2)
    )


type AnnotatedBasic = Annotated[int, tyro.conf.arg(name="basic")]


def test_annotated_alias() -> None:
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

    with pytest.raises(UnsupportedTypeAnnotationError):
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
type IntContainerIntermediate = Inner[int]
type IntContainer2 = IntContainerIntermediate
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


type Int0 = int
Int1 = NewType("Int1", Int0)
type Int2 = Int1
Int3 = NewType("Int3", Int2)
type Int4 = Int3
Int5 = NewType("Int5", Int4)
type Int6 = Int5
Int7 = NewType("Int7", Int6)


def test_pep695_new_type_alias() -> None:
    def main(arg: list[Int7], /) -> Any:
        return arg

    assert tyro.cli(main, args=["1", "2"]) == [1, 2]


def test_generic_config() -> None:
    @dataclass(frozen=True)
    class Container[T]:
        a: Inner[T]

    assert tyro.cli(
        Container[bool],
        args="--a.a True --a.b False".split(" "),
        config=(tyro.conf.FlagConversionOff,),
    ) == Container(Inner(True, False))


def test_generic_config_subcommand() -> None:
    @dataclass(frozen=True)
    class Container[T]:
        a: T

    assert tyro.cli(
        Container[Container[bool] | Container[str]],
        args="a:container-bool --a.a True".split(" "),
        default=Container(Container(a="30")),
        config=(tyro.conf.FlagConversionOff,),
    ) == Container(Container(True))

    assert tyro.cli(
        Container[Container[bool] | Container[str]],
        args=[],
        default=Container(Container(a="30")),
        config=(tyro.conf.FlagConversionOff,),
    ) == Container(Container("30"))

    assert tyro.cli(
        Container[Container[bool] | Container[str]],
        args=[],
        default=Container(Container(a=False)),
        config=(tyro.conf.FlagConversionOff,),
    ) == Container(Container(False))


def test_generic_config_subcommand2() -> None:
    @dataclass(frozen=True)
    class Container[T]:
        a: tyro.conf.OmitSubcommandPrefixes[T]

    assert tyro.cli(
        Container[Container[bool] | Container[str]],
        args="container-bool --a True".split(" "),
    ) == Container(Container(True))


def test_generic_config_subcommand3() -> None:
    @dataclass(frozen=True)
    class Container[T]:
        a: T

    assert tyro.cli(
        Container[Container[bool] | Container[str]],
        args=[],
        default=Container(Container(a=True)),
        config=(tyro.conf.OmitSubcommandPrefixes,),
    ) == Container(Container(True))


def test_generic_config_subcommand4() -> None:
    @dataclass(frozen=True)
    class Container[T]:
        a: T

    assert tyro.cli(
        Container[Container[bool] | Container[Literal["1", "2"]]],
        args="container-literal-1-2 --a 2".split(" "),
        config=(tyro.conf.OmitSubcommandPrefixes,),
    ) == Container(Container("2"))
    assert tyro.cli(
        Container[Container[bool] | Container[Literal["1", "2"]]],
        args=[],
        default=Container(Container(a=True)),
        config=(tyro.conf.OmitSubcommandPrefixes,),
    ) == Container(Container(True))


def test_generic_config_subcommand_matching_nested() -> None:
    @dataclass(frozen=True)
    class Container[T]:
        a: T

    assert "default: a:container-bool" in get_helptext_with_checks(
        Container[Container[bool] | Container[str]],
        default=Container(Container(a=False)),
    )
    assert "default: a:container-str" in get_helptext_with_checks(
        Container[Container[bool] | Container[str]],
        default=Container(Container(a="False")),
    )
    assert "default: a:container-literal-1-2" in get_helptext_with_checks(
        Container[Container[Literal[1, 2]] | Container[str]],
        default=Container(Container(a=1)),
    )
    assert "default: a:container-str" in get_helptext_with_checks(
        Container[Container[Literal[1, 2]] | Container[str]],
        default=Container(Container(a="1")),
    )

    assert tyro.cli(
        Container[Container[Literal["1", "2"]] | Container[bool]],
        args=[],
        default=Container(Container(a="1")),
        config=(tyro.conf.OmitSubcommandPrefixes,),
    ) == Container(Container("1"))


def test_generic_config_subcommand_matching_dict() -> None:
    @dataclass(frozen=True)
    class Container[T]:
        a: T

    assert "default: container-dict-str-str" in get_helptext_with_checks(
        Container[dict[str, int]] | Container[dict[str, str]],  # type: ignore
        default=Container({"a": "text"}),
    )
    assert "default: container-dict-str-int" in get_helptext_with_checks(
        Container[dict[str, int]] | Container[dict[str, str]],  # type: ignore
        default=Container({"a": 5}),
    )


def test_generic_config_subcommand_matching_tuple() -> None:
    @dataclass(frozen=True)
    class Container[T]:
        a: T

    assert "default: container-tuple-str-str" in get_helptext_with_checks(
        Container[tuple[str, int]] | Container[tuple[str, str]],  # type: ignore
        default=Container(("a", "text")),
    )
    assert "default: container-tuple-str-int" in get_helptext_with_checks(
        Container[tuple[str, int]] | Container[tuple[str, str]],  # type: ignore
        default=Container(("a", 5)),
    )


def test_generic_config_subcommand_matching_tuple_variable() -> None:
    @dataclass(frozen=True)
    class Container[T]:
        a: T

    assert "default: container-tuple-str-ellipsis" in get_helptext_with_checks(
        Container[tuple[str, ...]] | Container[tuple[int, ...]],  # type: ignore
        default=Container(("a", "text")),
    )
    assert "default: container-tuple-int-ellipsis" in get_helptext_with_checks(
        Container[tuple[str, ...]] | Container[tuple[int, ...]],  # type: ignore
        default=Container((1, 2, 3)),
    )


def test_deeply_inherited_init() -> None:
    class AConfig(BaseModel):
        a: int

    class AModel[TContainsAConfig: AConfig]:
        def __init__(self, config: TContainsAConfig):
            self.config = config

    class ABConfig(AConfig):
        b: int

    class ABModel[TContainsABConfig: ABConfig](AModel[TContainsABConfig]):
        pass

    class ABCConfig(ABConfig):
        c: int

    class ABCModel(ABModel[ABCConfig]):
        pass

    def a(model: ABCModel):
        print(model.config)

    def b(model: ABModel[ABConfig]):
        print(model.config)

    def c(model: ABModel[ABCConfig]):
        print(model.config)

    assert "--model.config.a" in get_helptext_with_checks(a)
    assert "--model.config.b" in get_helptext_with_checks(a)
    assert "--model.config.c" in get_helptext_with_checks(a)

    assert "--model.config.a" in get_helptext_with_checks(b)
    assert "--model.config.b" in get_helptext_with_checks(b)
    assert "--model.config.c" not in get_helptext_with_checks(b)

    assert "--model.config.a" in get_helptext_with_checks(c)
    assert "--model.config.b" in get_helptext_with_checks(c)
    assert "--model.config.c" in get_helptext_with_checks(c)


def test_bad_orig_bases() -> None:
    @dataclass(frozen=True)
    class A[T]:
        a: T

    @dataclass(frozen=True)
    class B(A[int | str | bool]):
        x: int

    @dataclass(frozen=True)
    class C(A[int | str | bool]):
        a: str

    @dataclass(frozen=True)
    class D(B, C): ...  # , C): ...

    assert "--a" in get_helptext_with_checks(D)
    assert "STR" in get_helptext_with_checks(D)
    assert "INT|STR" not in get_helptext_with_checks(D)


type ConstrainedTuple[T] = tuple[T] | tuple[T, T]


def test_generic_type_alias_union() -> None:
    """Test that unions of generic type aliases resolve type parameters correctly.

    Regression test for bug where ConstrainedTuple[int] | ConstrainedTuple[bool]
    would incorrectly resolve to typing.tuple[int]| tuple[int, int]| tuple[T]| tuple[T, T]
    instead of typing.tuple[int]| tuple[int, int]| tuple[bool]| tuple[bool, bool].
    """

    def main(arg: ConstrainedTuple[int] | ConstrainedTuple[bool]) -> Any:
        return arg

    # Test with int tuple of length 1
    assert tyro.cli(main, args=["--arg", "1"]) == (1,)

    # Test with int tuple of length 2
    assert tyro.cli(main, args=["--arg", "1", "2"]) == (1, 2)

    # Test with bool tuple of length 1
    assert tyro.cli(main, args=["--arg", "True"]) == (True,)

    # Test with bool tuple of length 2
    assert tyro.cli(main, args=["--arg", "False", "True"]) == (False, True)


def test_generic_type_alias_individual_resolution() -> None:
    """Test that individual generic type aliases resolve correctly.

    This verifies that the type parameter resolution works correctly for
    individual generic type aliases before testing unions.
    """
    from tyro._resolver import TypeParamResolver

    # Test individual resolution
    alias_int = ConstrainedTuple[int]
    alias_bool = ConstrainedTuple[bool]

    resolved_int = TypeParamResolver.concretize_type_params(alias_int)  # type: ignore
    resolved_bool = TypeParamResolver.concretize_type_params(alias_bool)  # type: ignore

    # Check that the resolved types are what we expect

    assert resolved_int == tuple[int] | tuple[int, int]
    assert resolved_bool == tuple[bool] | tuple[bool, bool]


def test_generic_type_alias_union_resolution() -> None:
    """Test that unions of generic type aliases resolve correctly at the type level.

    This tests the internal type resolution mechanism that was buggy.
    """

    from tyro._resolver import TypeParamResolver

    # Test union resolution
    union_type = ConstrainedTuple[int] | ConstrainedTuple[bool]
    resolved_union = TypeParamResolver.concretize_type_params(union_type)  # type: ignore

    # The resolved union should contain all four tuple types
    expected = tuple[int] | tuple[int, int] | tuple[bool] | tuple[bool, bool]
    assert resolved_union == expected

    # Verify that no unresolved TypeVars remain (this was the bug)
    # The resolved type should not contain any raw TypeVar instances
    import typing
    from typing import get_args

    def contains_typevar(typ) -> bool:
        """Recursively check if a type contains any TypeVar instances."""
        if isinstance(typ, typing.TypeVar):
            return True
        for arg in get_args(typ):
            if contains_typevar(arg):
                return True
        return False

    assert not contains_typevar(resolved_union), (
        f"Resolved type contains unresolved TypeVars: {resolved_union}"
    )
