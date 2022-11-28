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
