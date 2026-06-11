"""Regression tests for a second batch of bugs found via manual exploration.

Each test fails on the unfixed code and documents the expected behavior.

* ``test_missing_value_error_renders_arg_name`` -- the "Missing value" parse
  error rendered the argument's ``name_or_flags`` tuple verbatim (e.g.
  ``'('--coord',)'``) and leaked the internal ``__tyro-dummy-inner__`` name
  for positionals.

* ``test_bytearray_field`` -- a ``bytearray`` field crashed on every input
  (``bytearray(str)`` needs an encoding) even though it is registered as a
  supported primitive.

* ``test_pure_path_subclass_preserved`` -- ``PurePosixPath`` / ``PureWindowsPath``
  annotations returned a concrete OS ``Path`` of the wrong flavour instead of
  the annotated pure-path type.

* ``test_var_keyword_default_instance`` -- a ``default=`` instance for a
  ``**kwargs`` parameter was dropped (returned ``{}``) because the VAR_KEYWORD
  branch reset the default unconditionally, unlike the ``*args`` branch.

* ``test_attrs_field_alias`` -- attrs fields whose init-arg name differs from
  the attribute name (private ``_x`` -> ``x``, or ``attrs.field(alias=...)``)
  crashed construction with an unexpected-keyword ``TypeError``.

* ``test_pydantic_field_alias`` -- pydantic v2 fields with ``Field(alias=...)``
  / ``validation_alias`` crashed with a ``ValidationError`` because tyro
  constructed by field name while pydantic validates by alias.
"""

# mypy: disable-error-code="call-overload"
# `tyro.cli(Tuple[int, int, int], ...)` / `tyro.cli(Literal[...], ...)` pass a
# bare typing special form, which newer mypy (2.x) rejects against the `cli`
# overloads even though it is valid at runtime.

from __future__ import annotations

import dataclasses
import pathlib
from typing import Literal, Tuple

import attrs
import pydantic
import pytest
from helptext_utils import get_helptext_with_checks

import tyro


def test_missing_value_error_renders_arg_name(capsys: pytest.CaptureFixture) -> None:
    @dataclasses.dataclass
    class C:
        coord: Tuple[int, int, int]

    with pytest.raises(SystemExit):
        tyro.cli(C, args=["--coord", "1"])
    out = capsys.readouterr()
    text = out.out + out.err
    assert "--coord" in text
    assert "('--coord',)" not in text  # no raw tuple repr

    # Positional: must not leak the internal dummy name.
    with pytest.raises(SystemExit):
        tyro.cli(Tuple[int, int, int], args=["1", "2"])
    out = capsys.readouterr()
    text = out.out + out.err
    assert "__tyro-dummy-inner__" not in text

    # Under `use_underscores=True` the lowered dummy name keeps underscores
    # (`__tyro_dummy_inner__`); it must be hidden too, in both the
    # missing-value and invalid-choice error paths.
    with pytest.raises(SystemExit):
        tyro.cli(Tuple[int, int, int], args=["1", "2"], use_underscores=True)
    out = capsys.readouterr()
    text = out.out + out.err
    assert "__tyro-dummy-inner__" not in text
    assert "__tyro_dummy_inner__" not in text

    with pytest.raises(SystemExit):
        tyro.cli(Literal["a", "b"], args=["zzz"], use_underscores=True)
    out = capsys.readouterr()
    text = out.out + out.err
    assert "__tyro-dummy-inner__" not in text
    assert "__tyro_dummy_inner__" not in text


def test_bytearray_field() -> None:
    @dataclasses.dataclass
    class C:
        x: bytearray = dataclasses.field(default_factory=bytearray)

    assert tyro.cli(C, args=["--x", "hello"]) == C(x=bytearray(b"hello"))

    # bytes still works.
    @dataclasses.dataclass
    class D:
        x: bytes = b""

    assert tyro.cli(D, args=["--x", "hello"]) == D(x=b"hello")


def test_pure_path_subclass_preserved() -> None:
    @dataclasses.dataclass
    class W:
        x: pathlib.PureWindowsPath

    out = tyro.cli(W, args=["--x", "C:\\a\\b"])
    assert isinstance(out.x, pathlib.PureWindowsPath)
    assert out.x == pathlib.PureWindowsPath("C:\\a\\b")

    @dataclasses.dataclass
    class P:
        x: pathlib.PurePosixPath

    out2 = tyro.cli(P, args=["--x", "/a/b"])
    assert isinstance(out2.x, pathlib.PurePosixPath)

    # Concrete Path is unchanged (resolves to the OS-specific concrete class).
    @dataclasses.dataclass
    class C:
        x: pathlib.Path

    out3 = tyro.cli(C, args=["--x", "/a/b"])
    assert isinstance(out3.x, pathlib.Path)
    assert out3.x == pathlib.Path("/a/b")


def test_var_keyword_default_instance() -> None:
    class Bag:
        def __init__(self, **kwargs: int) -> None:
            self.kwargs = kwargs

        def __eq__(self, other: object) -> bool:
            return isinstance(other, Bag) and other.kwargs == self.kwargs

    # A provided default instance must propagate when nothing is overridden.
    assert tyro.cli(Bag, args=[], default=Bag(x=1, y=2)).kwargs == {"x": 1, "y": 2}
    # No default -> empty.
    assert tyro.cli(Bag, args=[]).kwargs == {}
    # CLI override still works, and overrides the default.
    assert tyro.cli(Bag, args=["--kwargs", "z", "9"], default=Bag(x=1)).kwargs == {
        "z": 9
    }


def test_attrs_field_alias() -> None:
    @attrs.define
    class A:
        x: int = attrs.field(alias="renamed")

    assert tyro.cli(A, args=["--x", "5"]) == A(5)

    @attrs.define
    class B:
        _x: int = attrs.field()

    assert tyro.cli(B, args=["--_x", "5"]) == B(5)

    # Normal attrs fields are unaffected.
    @attrs.define
    class Normal:
        name: str = "hi"
        count: int = 0

    assert tyro.cli(Normal, args=["--name", "bob", "--count", "3"]) == Normal("bob", 3)


def test_pydantic_field_alias() -> None:
    if not pydantic.VERSION.startswith("2"):
        pytest.skip("pydantic v2 only")

    class M(pydantic.BaseModel):
        real_name: int = pydantic.Field(alias="aliased")

    assert tyro.cli(M, args=["--real-name", "5"]).real_name == 5

    class M2(pydantic.BaseModel):
        x: int = pydantic.Field(validation_alias="vx")

    assert tyro.cli(M2, args=["--x", "5"]).x == 5

    # No alias: unaffected.
    class M3(pydantic.BaseModel):
        a: int = 1

    assert tyro.cli(M3, args=["--a", "9"]).a == 9

    # A non-string validation_alias (AliasChoices/AliasPath) must NOT be
    # remapped to the serialization-side `.alias` (which pydantic rejects on
    # input). With populate_by_name the field name is accepted; constructing by
    # field name must keep working (regression guard for the alias-remap fix).
    class M4(pydantic.BaseModel):
        model_config = pydantic.ConfigDict(populate_by_name=True)
        x: int = pydantic.Field(
            alias="pa", validation_alias=pydantic.AliasChoices("c1", "c2")
        )

    assert tyro.cli(M4, args=["--x", "5"]).x == 5

    # A model with an aliased field must keep its docstring in --help: the
    # alias-remapping closure must carry the model's `__doc__` (regression
    # guard -- helptext extraction reads `instantiate.__doc__`).
    class MDoc(pydantic.BaseModel):
        """Docstring for the aliased model."""

        real_name: int = pydantic.Field(alias="aliased", default=3)

    assert "Docstring for the aliased model." in get_helptext_with_checks(MDoc)


def test_pydantic_v1_field_alias() -> None:
    """pydantic.v1-style models with ``Field(alias=...)`` must also construct
    by alias: v1 validates by alias only (unless
    ``allow_population_by_field_name`` is set), so constructing by field name
    silently dropped the CLI value with the default ``Extra.ignore`` config."""
    try:
        import pydantic.v1 as pydantic_v1
    except ImportError:  # pragma: no cover
        pytest.skip("pydantic.v1 is not available")

    class M(pydantic_v1.BaseModel):
        real_name: int = pydantic_v1.Field(3, alias="aliased")

    assert tyro.cli(M, args=["--real-name", "5"]).real_name == 5
    assert tyro.cli(M, args=[]).real_name == 3


def test_pydantic_alias_without_validation_alias() -> None:
    """Pin the fallback for (older) pydantic 2.x versions that don't
    auto-populate ``validation_alias`` from ``alias`` at model build time: with
    ``validation_alias`` unset, the serialization-side ``alias`` is the name
    pydantic accepts on input."""
    if not pydantic.VERSION.startswith("2"):
        pytest.skip("pydantic v2 only")

    class M(pydantic.BaseModel):
        x: int = pydantic.Field(alias="ax")

    field_info = M.model_fields["x"]
    original = field_info.validation_alias
    field_info.validation_alias = None  # Simulate older pydantic 2.x.
    try:
        assert tyro.cli(M, args=["--x", "5"]).x == 5
    finally:
        field_info.validation_alias = original
