"""Regression tests for GitHub issues #474 and #475.

PEP 695 type parameters (``class Foo[T]: ...``, Python 3.12+) live in
``__type_params__``, not in module globals. Combined with stringized
annotations (``from __future__ import annotations`` / PEP 563), a field whose
type references such a parameter used to raise an obscure
``NameError: name 'T' is not defined`` from ``get_type_hints`` (#475). This also
surfaced through ``dataclasses.InitVar`` members (#474), which tyro should
recognize as ordinary constructor arguments.
"""

from __future__ import annotations

import dataclasses

import pytest

import tyro


@dataclasses.dataclass
class Container[T]:
    items: list[T]


@dataclasses.dataclass
class Sequencer[Data]:
    items: list[Data]


type Seq = Sequencer[int]


@dataclasses.dataclass
class Bare[T]:
    x: T


@dataclasses.dataclass
class Pair[K, V]:
    k: K
    v: V


@dataclasses.dataclass
class Compound[T]:
    mapping: dict[str, T]
    opt: T | None = None
    rest: tuple[T, ...] = ()


@dataclasses.dataclass
class Base[T]:
    base_field: T


@dataclasses.dataclass
class Child[T](Base[T]):
    child_field: T


@dataclasses.dataclass
class ReifiedChild(Base[int]):
    extra: str = "x"


def test_pep695_generic_stringized_annotation_resolves() -> None:
    # #475: previously raised `NameError: name 'T' is not defined` because the
    # stringized `list[T]` annotation couldn't see the PEP 695 type parameter.
    out = tyro.cli(Container[int], args=["--items", "1", "2", "3"])
    assert out.items == [1, 2, 3]
    assert all(isinstance(x, int) for x in out.items)

    out_str = tyro.cli(Container[str], args=["--items", "a", "b"])
    assert out_str.items == ["a", "b"]


def test_initvar_is_recognized_as_constructor_arg() -> None:
    # #474: InitVar fields are init-only pseudo-fields passed to __init__ /
    # __post_init__, so tyro should expose them as CLI arguments.
    @dataclasses.dataclass
    class WithInit:
        x: int
        offset: dataclasses.InitVar[int] = 10

        def __post_init__(self, offset: int) -> None:
            self.total = self.x + offset

    # If InitVar weren't recognized, `--offset` would be an unrecognized option.
    out = tyro.cli(WithInit, args=["--x", "1", "--offset", "5"])
    assert out.x == 1
    assert out.total == 6
    # Default is used when not provided.
    assert tyro.cli(WithInit, args=["--x", "2"]).total == 12


def test_initvar_of_pep695_generic_does_not_crash() -> None:
    # The exact shape from the issue: an InitVar of a (PEP 695) generic, behind
    # a PEP 695 `type` alias, with stringized annotations. Used to raise the
    # obscure NameError; should now resolve cleanly.
    @dataclasses.dataclass
    class App:
        name: str = "default"
        _sequencer: dataclasses.InitVar[Seq | None] = None

        def __post_init__(self, _sequencer: Seq | None) -> None:
            self.seq = _sequencer

    out = tyro.cli(App, args=["--name", "hi"])
    assert out.name == "hi"
    assert out.seq is None


def test_pep695_multiple_params_and_compound_refs() -> None:
    # Multiple PEP 695 params, and type params nested inside dict/Optional/tuple.
    assert tyro.cli(Pair[int, str], args=["--k", "1", "--v", "a"]) == Pair(1, "a")

    out = tyro.cli(
        Compound[int],
        args=["--mapping", "a", "1", "--opt", "2", "--rest", "3", "4"],
    )
    assert out.mapping == {"a": 1}
    assert out.opt == 2 and isinstance(out.opt, int)
    assert out.rest == (3, 4)
    # Defaults still work when the param-typed optionals are omitted.
    assert tyro.cli(Compound[str], args=["--mapping", "k", "v"]) == Compound(
        {"k": "v"}, None, ()
    )


def test_pep695_inheritance() -> None:
    # Type parameter forwarded through a base class: Child[int] -> Base[int].
    assert tyro.cli(
        Child[int], args=["--base-field", "1", "--child-field", "2"]
    ) == Child(base_field=1, child_field=2)
    # Base reified at the inheritance site: ReifiedChild(Base[int]).
    out = tyro.cli(ReifiedChild, args=["--base-field", "9"])
    assert out.base_field == 9 and isinstance(out.base_field, int)
    assert out.extra == "x"


def test_pep695_generic_as_nested_field() -> None:
    @dataclasses.dataclass
    class Outer:
        inner: Bare[int]

    out = tyro.cli(Outer, args=["--inner.x", "7"])
    assert out.inner == Bare(7) and isinstance(out.inner.x, int)


def test_pep695_generic_in_subcommand_union() -> None:
    @dataclasses.dataclass
    class Outer2:
        choice: Bare[int] | Pair[int, int]

    assert tyro.cli(Outer2, args=["choice:bare-int", "--choice.x", "3"]) == Outer2(
        choice=Bare(3)
    )
    assert tyro.cli(
        Outer2, args=["choice:pair-int-int", "--choice.k", "1", "--choice.v", "2"]
    ) == Outer2(choice=Pair(1, 2))


def test_pep695_unreified_generic_gives_clean_error_not_nameerror() -> None:
    # An *unparameterized* PEP 695 generic field can't bind its type parameter,
    # so it resolves to `Any` -> a clean "unsupported type" error (SystemExit),
    # NOT the obscure pre-fix `NameError: name 'T' is not defined`.
    @dataclasses.dataclass
    class Outer:
        inner: Bare

    with pytest.raises(SystemExit):
        tyro.cli(Outer, args=["--inner.x", "1"])
