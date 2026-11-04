"""Test helptext from `dataclasses.field(doc=...)`.

This test file requires Python 3.14+. The `# type: ignore` comments can be removed once
the type checkers in the CI target Python 3.14.
"""

import dataclasses
from dataclasses import field

from helptext_utils import get_helptext_with_checks
from typing_extensions import Annotated, Doc

import tyro


def test_field_doc_basic() -> None:
    @dataclasses.dataclass
    class Config:
        x: int = field(doc="Documentation for x.")  # type: ignore
        y: str = field(default="hi", doc="Documentation for y.")  # type: ignore

    helptext = get_helptext_with_checks(Config)
    assert "Documentation for x." in helptext
    assert "Documentation for y." in helptext


MULTILINE_DOC = """
    This is a multiline
    documentation string
    that should be dedented.
    """


def test_field_doc_multiline_dedent() -> None:
    @dataclasses.dataclass
    class Config:
        x: int = field(doc=MULTILINE_DOC)  # type: ignore

    helptext = get_helptext_with_checks(Config)
    assert "multiline documentation" in helptext
    assert "string that" in helptext


@dataclasses.dataclass
class Inner:
    """Inner docstring."""

    a: int = field(default=1, doc="Documentation for a.")  # type: ignore


@dataclasses.dataclass
class Outer:
    inner: Inner = field(default_factory=Inner, doc="Documentation for inner.")  # type: ignore


def test_field_doc_nested() -> None:
    helptext = get_helptext_with_checks(Outer)
    assert "Documentation for a." in helptext
    assert "Documentation for inner." in helptext
    assert "Inner docstring." not in helptext


def test_field_doc_overrides_docstring_and_comment() -> None:
    @dataclasses.dataclass
    class Config:
        # Comment for x.
        x: int = field(doc="Field doc for x.")  # type: ignore
        y: int = field(doc="Field doc for y.")  # type: ignore
        """Attribute docstring for y."""

    helptext = get_helptext_with_checks(Config)
    assert "Field doc for x." in helptext
    assert "Comment for x." not in helptext
    assert "Field doc for y." in helptext
    assert "Attribute docstring for y." not in helptext


def test_pep727_doc_overrides_field_doc() -> None:
    @dataclasses.dataclass
    class Config:
        x: Annotated[int, Doc("PEP 727 doc for x.")] = field(doc="Field doc for x.")  # type: ignore

    helptext = get_helptext_with_checks(Config)
    assert "PEP 727 doc for x." in helptext
    assert "Field doc for x." not in helptext


def test_arg_help_overrides_field_doc() -> None:
    @dataclasses.dataclass
    class Config:
        x: Annotated[int, tyro.conf.arg(help="Help for x.")] = field(doc="Doc for x.")  # type: ignore
        y: Annotated[
            int, tyro.conf.arg(help="Help for y."), Doc("PEP 727 documentation for y.")
        ] = field(doc="Doc for y.")  # type: ignore

    helptext = get_helptext_with_checks(Config)
    assert "Help for x." in helptext
    assert "Doc for x." not in helptext
    assert "Help for y." in helptext
    assert "PEP 727 documentation for y." not in helptext
    assert "Doc for y." not in helptext
