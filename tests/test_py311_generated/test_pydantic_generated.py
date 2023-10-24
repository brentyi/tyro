import contextlib
import io
import pathlib
from typing import cast

import pytest
from pydantic import BaseModel, Field

import tyro


def test_pydantic() -> None:
    class ManyTypesA(BaseModel):
        i: int
        s: str = "hello"
        f: float = Field(default_factory=lambda: 3.0)
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
