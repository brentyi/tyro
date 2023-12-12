from __future__ import annotations

import sys

import pytest

import tyro


@pytest.mark.skipif(
    sys.version_info >= (3, 10), reason="No error for newer versions of Python."
)
def test_new_union_error() -> None:
    """PEP 604 allows `|` to be used as a type annotation in Python >=3.10."""

    def main(x: int | str) -> None:
        ...

    with pytest.raises(TypeError) as e:
        tyro.cli(main)
    assert "You may be using a Union in the form of `X | Y`" in e.value.args[0]


@pytest.mark.skipif(
    sys.version_info >= (3, 9), reason="No error for newer versions of Python."
)
def test_new_collection_error() -> None:
    """PEP 585 allows standard collections to be used as generics in Python >=3.9."""

    def main(x: list[int]) -> None:
        ...

    with pytest.raises(TypeError) as e:
        tyro.cli(main)
    assert "You may be using a standard collection as a generic" in e.value.args[0]
