from __future__ import annotations

import dataclasses

import tyro

T = str


def test_type_param_shadows_module_global() -> None:
    assert tyro.cli(Config[int], args=["--x", "3"]) == Config(3)
    assert tyro.cli(Child, args=["--x", "3"]) == Child(3)


@dataclasses.dataclass
class Config[T]:
    x: T


@dataclasses.dataclass
class Child(Config[int]): ...
