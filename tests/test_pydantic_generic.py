from typing import Generic, TypeVar

from helptext_utils import get_helptext_with_checks
from pydantic import BaseModel

import tyro

T = TypeVar("T")


def test_pydantic_generic() -> None:
    class ManyTypesA(BaseModel, Generic[T]):
        i: T
        s: str = "hello"
        f: float = 3.0

    assert tyro.cli(ManyTypesA[int], args=["--i", "5"]) == ManyTypesA(
        i=5, s="hello", f=3.0
    )


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


if __name__ == "__main__":
    test_pydantic_generic()
    # test_pydantic_inheritance_with_same_typevar()
