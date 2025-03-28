import dataclasses
from typing import Annotated

from helptext_utils import get_helptext_with_checks
from typing_extensions import Doc


class SomeOtherMarker:
    pass


def test_basic():
    @dataclasses.dataclass
    class SimpleDoc:
        x: Annotated[int, Doc("Simple documentation")]

    assert "Simple documentation" in get_helptext_with_checks(SimpleDoc)


def test_basic_function():
    def main(x: Annotated[int, Doc("Simple documentation")]) -> None:
        del x

    assert "Simple documentation" in get_helptext_with_checks(main)


def test_multiple_annotations():
    @dataclasses.dataclass
    class MultipleAnnotations:
        x: Annotated[int, SomeOtherMarker(), Doc("Doc with other markers")]

    assert "Doc with other markers" in get_helptext_with_checks(MultipleAnnotations)


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

    assert "multiline documentation" in get_helptext_with_checks(MultilineDoc)
    assert "string that" in get_helptext_with_checks(MultilineDoc)
