from typing import Generic, TypeVar

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
