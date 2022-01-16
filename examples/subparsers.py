from __future__ import annotations

import dataclasses
from typing import Union

import dcargs


@dataclasses.dataclass
class Args:
    command: Union[Checkout, Commit]


@dataclasses.dataclass
class Checkout:
    branch: str


@dataclasses.dataclass
class Commit:
    message: str
    all: bool = False


if __name__ == "__main__":
    args = dcargs.parse(Args)
    print(args)
