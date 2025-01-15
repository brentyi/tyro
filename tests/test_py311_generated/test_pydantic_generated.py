from __future__ import annotations

import contextlib
import io
import pathlib
import sys
from typing import Annotated, Generic, TypeVar, cast

import pytest
from helptext_utils import get_helptext_with_checks
from pydantic import BaseModel, Field, v1

import tyro
import tyro._strings


def test_pydantic() -> None:
    class ManyTypesA(BaseModel):
        i: int
        s: str = "hello"
        f: float = Field(default_factory=lambda: 3.0)
        p: pathlib.Path
        ignored: float = Field(default_factory=lambda: 3.0, init_var=False)

    # We can directly pass a dataclass to `tyro.cli()`:
    assert tyro.cli(
        ManyTypesA,
        args=[
            "--i",
            "5",
            "--p",
            "~",
        ],
    ) == ManyTypesA(i=5, s="hello", f=3.0, p=pathlib.Path("~"))


def test_pydantic_v1() -> None:
    class ManyTypesA(v1.BaseModel):
        i: int
        s: str = "hello"
        f: float = v1.Field(default_factory=lambda: 3.0)
        p: pathlib.Path

    # We can directly pass a dataclass to `tyro.cli()`:
    assert tyro.cli(
        ManyTypesA,
        args=[
            "--i",
            "5",
            "--p",
            "~",
        ],
    ) == ManyTypesA(i=5, s="hello", f=3.0, p=pathlib.Path("~"))


def test_pydantic_v1_conf() -> None:
    class ManyTypesA(v1.BaseModel):
        i: int
        """This is a docstring."""
        s: tyro.conf.Suppress[str] = "hello"
        f: float = v1.Field(default_factory=lambda: 3.0)

    class ManyTypesB(ManyTypesA):
        p: pathlib.Path

    # We can directly pass a dataclass to `tyro.cli()`:
    assert tyro.cli(
        ManyTypesB,
        args=[
            "--i",
            "5",
            "--p",
            "~",
        ],
    ) == ManyTypesB(i=5, s="hello", f=3.0, p=pathlib.Path("~"))
    helptext = get_helptext_with_checks(ManyTypesB)
    assert "--s" not in helptext
    assert "--i" in helptext

    # This doesn't work when combining older versions of Python with older
    # versions of pydantic. The root cause may be in the docstring_parser
    # dependency.
    if sys.version_info >= (3, 10):
        assert "This is a docstring" in helptext


def test_pydantic_helptext() -> None:
    class Helptext(BaseModel):
        """This docstring should be printed as a description."""

        x: int = Field(description="Documentation 1")

        y: int = Field(description="Documentation 2")

        z: int = Field(description="Documentation 3")

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            tyro.cli(Helptext, args=["--help"])
    helptext = f.getvalue()
    assert tyro._strings.strip_ansi_sequences(cast(str, Helptext.__doc__)) in helptext

    assert "Documentation 1" in helptext
    assert "Documentation 2" in helptext
    assert "Documentation 3" in helptext


def test_pydantic_suppress_base_model_helptext() -> None:
    class Helptext(BaseModel):
        x: int = Field(description="Documentation 1")

        y: int = Field(description="Documentation 2")

        z: int = Field(description="Documentation 3")

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            tyro.cli(Helptext, args=["--help"])
    helptext = f.getvalue()

    assert "Create a new model by parsing and validating" not in helptext
    assert "Documentation 1" in helptext
    assert "Documentation 2" in helptext
    assert "Documentation 3" in helptext


class HelptextWithFieldDocstring(BaseModel):
    """This docstring should be printed as a description."""

    x: int
    """Documentation 1"""

    y: int = Field(description="Documentation 2")

    z: int = Field(description="Documentation 3")


def test_pydantic_field_helptext_from_docstring() -> None:
    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            tyro.cli(HelptextWithFieldDocstring, args=["--help"])
    helptext = f.getvalue()
    assert (
        tyro._strings.strip_ansi_sequences(
            cast(str, HelptextWithFieldDocstring.__doc__)
        )
        in helptext
    )

    assert "Documentation 1" in helptext
    assert "Documentation 2" in helptext
    assert "Documentation 3" in helptext


def test_pydantic_positional_annotation() -> None:
    class AnnotatedAsPositional(BaseModel):
        name: tyro.conf.Positional[str]
        """This is annotated as a positional argument."""

    result = tyro.cli(AnnotatedAsPositional, args=["myname"])
    assert isinstance(result, AnnotatedAsPositional)


def test_pydantic_alias() -> None:
    class AliasCfg(BaseModel):
        alias: Annotated[str, tyro.conf.arg(aliases=["-a"])]

    assert tyro.cli(AliasCfg, args=["--alias", "3"]) == AliasCfg(alias="3")
    assert tyro.cli(AliasCfg, args=["-a", "3"]) == AliasCfg(alias="3")


def test_pydantic_default_instance() -> None:
    class Inside(BaseModel):
        x: int = 1

    class Outside(BaseModel):
        i: Inside = Inside(x=2)

    assert tyro.cli(Outside, args=[]).i.x == 2, (
        "Expected x value from the default instance",
    )
    assert tyro.cli(Outside, args=["--i.x", "3"]).i.x == 3


def test_pydantic_nested_default_instance() -> None:
    class Inside(BaseModel):
        x: int = 1

    class Middle(BaseModel):
        i: Inside

    class Outside(BaseModel):
        m: Middle = Middle(i=Inside(x=2))

    assert tyro.cli(Outside, args=[]).m.i.x == 2, (
        "Expected x value from the default instance",
    )
    assert tyro.cli(Outside, args=["--m.i.x", "3"]).m.i.x == 3


# Updating forward references in Pydantic v1 requires that these classes are global.


class InsideV1(v1.BaseModel):
    x: int = 1


class MiddleV1(v1.BaseModel):
    i: InsideV1


def test_pydantic_v1_nested_default_instance() -> None:
    class Outside(v1.BaseModel):
        m: MiddleV1 = MiddleV1(i=InsideV1(x=2))

    assert tyro.cli(Outside, args=[]).m.i.x == 2, (
        "Expected x value from the default instance",
    )
    assert tyro.cli(Outside, args=["--m.i.x", "3"]).m.i.x == 3


def test_pydantic_inheritance_with_same_typevar() -> None:
    T = TypeVar("T")

    class A(BaseModel, Generic[T]):
        x: T

    class B(A[int], Generic[T]):
        y: T

    assert "INT" in get_helptext_with_checks(B[int])
    assert "STR" not in get_helptext_with_checks(B[int])
    assert "STR" in get_helptext_with_checks(B[str])
    assert "INT" in get_helptext_with_checks(B[str])

    assert tyro.cli(B[str], args=["--x", "1", "--y", "2"]) == B(x=1, y="2")
    assert tyro.cli(B[int], args=["--x", "1", "--y", "2"]) == B(x=1, y=2)
