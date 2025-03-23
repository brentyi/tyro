import dataclasses

from typing_extensions import (
    Annotated,
    Doc,
)

from tyro._docstrings import get_doc_from_annotated


class SomeOtherMarker:
    pass


def test_basic():
    @dataclasses.dataclass
    class SimpleDoc:
        x: Annotated[int, Doc("Simple documentation")]

    assert get_doc_from_annotated(SimpleDoc, "x") == "Simple documentation"


def test_multiple_annotations():
    @dataclasses.dataclass
    class MultipleAnnotations:
        x: Annotated[int, SomeOtherMarker(), Doc("Doc with other markers")]

    assert get_doc_from_annotated(MultipleAnnotations, "x") == "Doc with other markers"


def test_absent_doc():
    @dataclasses.dataclass
    class NoDoc:
        x: Annotated[int, SomeOtherMarker()]

    assert get_doc_from_annotated(NoDoc, "x") is None


def test_non_annotated():
    @dataclasses.dataclass
    class NotAnnotated:
        x: int

    assert get_doc_from_annotated(NotAnnotated, "x") is None


def test_multiline_to_dedent():
    @dataclasses.dataclass
    class MultilineDoc:
        x: Annotated[
            int,
            Doc("""
            This is a multiline
            documentation string
            that should be dedented.
        """),
        ]

    assert get_doc_from_annotated(MultilineDoc, "x") == (
        "This is a multiline\ndocumentation string\nthat should be dedented."
    )


def test_absent_field():
    @dataclasses.dataclass
    class ExistingField:
        x: Annotated[int, Doc("Doc for x")]

    assert get_doc_from_annotated(ExistingField, "non_existent") is None
