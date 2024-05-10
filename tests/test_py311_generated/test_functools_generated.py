from __future__ import annotations

import dataclasses
import functools

import pytest
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

    helptext = get_helptext_with_checks(functools.partial(main, b="hello world"))
    assert "partial" not in helptext
    assert "Hello!" in helptext
    assert "hello world" in helptext


def test_partial_helptext_class() -> None:
    class Main:
        """Hello!"""

        def __init__(self, a: int, b: str) -> None:
            self.inner = b * a

    helptext = get_helptext_with_checks(functools.partial(Main, b="3"))
    assert "partial" not in helptext
    assert "Hello!" in helptext


def test_wraps_func() -> None:
    def main(a: int, b: str) -> str:
        return b * a

    @functools.wraps(main)
    def wrapper(*args, **kwargs) -> int:
        return kwargs["a"]

    assert tyro.cli(wrapper, args=["--a", "3", "--b", "hi"]) == 3
    with pytest.raises(SystemExit):
        tyro.cli(wrapper, args=["--a", "3"])


def test_wraps_partial_func_helptext() -> None:
    def main(a: int, b: str) -> str:
        """Hello!

        Args:
            a: Argument.
            b: Argument.
        """
        return b * a

    @functools.wraps(main)
    def wrapper(*args, **kwargs) -> int:
        return kwargs["a"]

    assert tyro.cli(functools.partial(wrapper, a=3), args=["--b", "hi"]) == 3

    helptext = get_helptext_with_checks(functools.partial(wrapper, b="3"))
    assert "wraps" not in helptext
    assert "Hello!" in helptext
    assert "Argument." in helptext


def test_wraps_partial_class_helptext() -> None:
    class Main:
        """Hello!"""

        def __init__(self, a: int, b: str) -> None:
            self.inner = b * a

    @functools.wraps(Main)
    def wrapper(*args, **kwargs) -> int:
        return kwargs["a"]

    assert tyro.cli(functools.partial(wrapper, a=3), args=["--b", "hi"]) == 3

    helptext = get_helptext_with_checks(functools.partial(wrapper, b="3"))
    assert "wraps" not in helptext
    assert "Hello!" in helptext


@dataclasses.dataclass
class WrappedDataclass:
    """Hello!"""

    a: int
    b: str
    """Second field."""


def test_wraps_partial_dataclass() -> None:
    @functools.wraps(WrappedDataclass)
    def wrapper(*args, **kwargs) -> str:
        return kwargs["a"] * kwargs["b"]

    assert tyro.cli(functools.partial(wrapper, a=3), args=["--b", "hi"]) == "hihihi"
    assert (
        tyro.cli(
            functools.partial(functools.partial(wrapper, a=3), b="hello"),
            args=["--b", "hi"],
        )
        == "hihihi"
    )
    assert (
        tyro.cli(functools.partial(functools.partial(wrapper, a=3), b="hello"), args=[])
        == "hellohellohello"
    )

    helptext = get_helptext_with_checks(functools.partial(wrapper, b="3"))
    assert "wraps" not in helptext
    assert "Hello!" in helptext
    assert "Second field." in helptext
