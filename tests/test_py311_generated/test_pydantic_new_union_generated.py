from __future__ import annotations

from typing import Annotated

from pydantic.dataclasses import dataclass

import tyro


@dataclass
class Test:
    x: Annotated[str | int, "A string or an integer"]


def test_simple() -> None:
    assert tyro.cli(Test, args=["--x", "hello"]) == Test(x="hello")
