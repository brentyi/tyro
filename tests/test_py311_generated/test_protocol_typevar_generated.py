# mypy: ignore-errors
from dataclasses import dataclass
from typing import Any, Generic, Protocol, Type, TypeVar, runtime_checkable

import tyro

OutT_co = TypeVar("OutT_co", covariant=True)


@runtime_checkable
class BuilderProtocol(Protocol[OutT_co]):
    def build(self, **kwd_override: Any) -> OutT_co: ...


OutT = TypeVar("OutT")


class SomeConfig(Generic[OutT]):
    _target: Type[OutT]

    def _configure(self) -> OutT: ...


class Foo: ...


@dataclass
class RealConfig(SomeConfig[Foo], BuilderProtocol[Foo]):
    bar: str = "foo_bar"

    def build(self, **kwd_override: Any) -> Foo:
        return Foo()


def test_protocol_typevar() -> None:
    """Adapted from: https://github.com/brentyi/tyro/issues/335"""
    expected = RealConfig(bar="baz")
    assert tyro.cli(RealConfig, args=["--bar", "baz"]) == expected


test_protocol_typevar()
