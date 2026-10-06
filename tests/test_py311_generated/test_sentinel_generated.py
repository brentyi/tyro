import dataclasses
from typing import List, Optional

import pytest
from helptext_utils import get_helptext_with_checks

import tyro

try:
    from typing_extensions import sentinel
except ImportError:  # pragma: no cover
    pytest.skip(
        "PEP 661 sentinels require typing-extensions>=4.16.0.",
        allow_module_level=True,
    )

RED = sentinel("RED")
GREEN = sentinel("GREEN")
BLUE = sentinel("BLUE")


def test_sentinel_union() -> None:
    @dataclasses.dataclass
    class Config:
        color: RED | BLUE = RED
        """Color argument."""

        opacity: float = 0.5
        """Opacity argument."""

    assert tyro.cli(Config, args=[]) == Config(color=RED)
    assert tyro.cli(Config, args=["--color", "RED"]) == Config(color=RED)
    assert tyro.cli(Config, args=["--color", "BLUE"]) == Config(color=BLUE)
    assert tyro.cli(Config, args=["--color", "BLUE"]).color is BLUE

    # GREEN is a sentinel, but not one of the allowed choices.
    with pytest.raises(SystemExit):
        tyro.cli(Config, args=["--color", "GREEN"])
    # Matching is case-sensitive, like for enums.
    with pytest.raises(SystemExit):
        tyro.cli(Config, args=["--color", "red"])


def test_sentinel_union_required() -> None:
    @dataclasses.dataclass
    class Config:
        color: RED | GREEN | BLUE

    assert tyro.cli(Config, args=["--color", "GREEN"]) == Config(color=GREEN)
    with pytest.raises(SystemExit):
        tyro.cli(Config, args=[])


def test_sentinel_union_helptext() -> None:
    @dataclasses.dataclass
    class Config:
        color: RED | BLUE = RED
        """Color argument."""

    helptext = get_helptext_with_checks(Config)
    assert "--color {RED,BLUE}" in helptext
    assert "Color argument. (default: RED)" in helptext


def test_single_sentinel() -> None:
    def main(color: RED = RED) -> object:
        return color

    assert tyro.cli(main, args=[]) is RED
    assert tyro.cli(main, args=["--color", "RED"]) is RED
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--color", "BLUE"])

    helptext = get_helptext_with_checks(main)
    assert "--color {RED}" in helptext
    assert "(default: RED)" in helptext


def test_optional_sentinel_union() -> None:
    def main(color: Optional[RED | BLUE] = None) -> object:
        return color

    assert tyro.cli(main, args=[]) is None
    assert tyro.cli(main, args=["--color", "None"]) is None
    assert tyro.cli(main, args=["--color", "BLUE"]) is BLUE
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--color", "GREEN"])

    helptext = get_helptext_with_checks(main)
    assert "--color {None,RED,BLUE}" in helptext


def test_sentinel_mixed_union() -> None:
    def main(x: RED | int = RED) -> object:
        return x

    assert tyro.cli(main, args=[]) is RED
    assert tyro.cli(main, args=["--x", "RED"]) is RED
    assert tyro.cli(main, args=["--x", "3"]) == 3
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--x", "BLUE"])

    helptext = get_helptext_with_checks(main)
    assert "--x {RED}|INT" in helptext


def test_sentinel_union_in_list() -> None:
    def main(colors: List[RED | BLUE] = [RED]) -> object:
        return colors

    assert tyro.cli(main, args=[]) == [RED]
    assert tyro.cli(main, args=["--colors", "BLUE", "RED", "BLUE"]) == [
        BLUE,
        RED,
        BLUE,
    ]
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--colors", "BLUE", "GREEN"])

    helptext = get_helptext_with_checks(main)
    assert "--colors [{RED,BLUE} [{RED,BLUE} ...]]" in helptext


def test_sentinel_positional() -> None:
    def main(color: tyro.conf.Positional[RED | BLUE]) -> object:
        return color

    assert tyro.cli(main, args=["BLUE"]) is BLUE
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["GREEN"])


def test_sentinel_union_as_root_type() -> None:
    assert tyro.cli(RED | BLUE, args=["RED"]) is RED
    assert tyro.cli(RED | BLUE, args=["BLUE"]) is BLUE
    with pytest.raises(SystemExit):
        tyro.cli(RED | BLUE, args=["GREEN"])


def test_sentinel_default_not_in_union() -> None:
    # A default that doesn't match any option in the union: tyro warns and
    # expands the union to include the default's type.
    def main(color: RED | BLUE = GREEN) -> object:  # type: ignore
        return color

    with pytest.warns(UserWarning):
        assert tyro.cli(main, args=[]) is GREEN
