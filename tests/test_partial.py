from __future__ import annotations

import dataclasses
import functools

from helptext_utils import get_helptext_with_checks

import tyro


def test_partial_func() -> None:
    def main(a: int, b: str) -> str:
        return b * a

    assert tyro.cli(functools.partial(main, a=3), args=["--b", "hi"]) == "hihihi"


def test_partial_class() -> None:
    class Main:
        def __init__(self, a: int, b: str) -> None:
            self.inner = b * a

    assert tyro.cli(functools.partial(Main, a=3), args=["--b", "hi"]).inner == "hihihi"


def test_partial_helptext_func() -> None:
    def main(a: int, b: str) -> str:
        """Hello!"""
        return b * a

    helptext = get_helptext_with_checks(functools.partial(main, b="3"))
    assert "partial" not in helptext
    assert "Hello!" in helptext


def test_partial_helptext_class() -> None:
    class Main:
        """Hello!"""

        def __init__(self, a: int, b: str) -> None:
            self.inner = b * a

    helptext = get_helptext_with_checks(functools.partial(Main, b="3"))
    assert "partial" not in helptext
    assert "Hello!" in helptext


def test_partial_helptext_dataclass() -> None:
    @dataclasses.dataclass
    class Config:
        a: int
        b: int
        """Hello!"""
        c: int

    ConfigWithDefaults = functools.partial(functools.partial(Config, a=3), c=5)
    assert tyro.cli(ConfigWithDefaults, args=["--b", "4"]) == Config(3, 4, 5)

    helptext = get_helptext_with_checks(ConfigWithDefaults)
    assert "partial" not in helptext
    assert "Hello!" in helptext
