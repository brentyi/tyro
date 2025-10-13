from __future__ import annotations

from pydantic.dataclasses import dataclass
from typing_extensions import Annotated

import tyro


@dataclass
class Test:
    x: Annotated[str | int, "A string or an integer"]


def test_simple() -> None:
    assert tyro.cli(Test, args=["--x", "hello"]) == Test(x="hello")
