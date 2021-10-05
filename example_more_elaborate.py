import dataclasses
import enum
from typing import Literal, Optional, Union

import dcargs

if __name__ == "__main__":

    class Color(enum.Enum):
        RED = enum.auto()
        GREEN = enum.auto()
        BLUE = enum.auto()

    @dataclasses.dataclass
    class A:
        """Docstring for A."""

        a: int

    @dataclasses.dataclass
    class B:
        """Docstring for B."""

        b: int
        bc: Union["B", "C"]

    @dataclasses.dataclass
    class C:
        """Docstring for C."""

        c: float

    @dataclasses.dataclass
    class Args:
        """Arguments."""

        w: Optional[float]
        flag: bool
        ab: Union[A, B]
        a: A
        number: Literal[1, 2, 5]  # One of three numbers
        color: Literal[Color.RED, Color.GREEN]
        x_what: int = 5
        y: int = dataclasses.field(default_factory=lambda: 8)

    arg = dcargs.parse(Args)
    arg.color
