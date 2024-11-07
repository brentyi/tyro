"""Tests for unsupported union types.

Unions like `int | str` or `SomeDataclassA | SomeDataclassB` are OK (note that the latter
will produce a pair of subcommands); when we write things like `int | SomeDataclassA`
handling gets more complicated but should still be supported!
"""

import dataclasses
from typing import Any, Dict, List, Tuple, Union

import pytest

import tyro


def test_subparser_strip_non_nested() -> None:
    @dataclasses.dataclass
    class DefaultHTTPServer:
        y: int

    @dataclasses.dataclass
    class DefaultSMTPServer:
        z: int

    @dataclasses.dataclass
    class DefaultSubparser:
        x: int
        # We add [int, str] to the annotation here... this should be ignored.
        bc: Union[int, str, DefaultHTTPServer, DefaultSMTPServer] = dataclasses.field(
            default_factory=lambda: DefaultHTTPServer(5)
        )

    assert (
        tyro.cli(
            DefaultSubparser, args=["--x", "1", "bc:default-http-server", "--bc.y", "5"]
        )
        == tyro.cli(DefaultSubparser, args=["--x", "1"])
        == DefaultSubparser(x=1, bc=DefaultHTTPServer(y=5))
    )
    assert tyro.cli(
        DefaultSubparser, args=["--x", "1", "bc:default-smtp-server", "--bc.z", "3"]
    ) == DefaultSubparser(x=1, bc=DefaultSMTPServer(z=3))
    assert (
        tyro.cli(
            DefaultSubparser, args=["--x", "1", "bc:default-http-server", "--bc.y", "8"]
        )
        == tyro.cli(
            DefaultSubparser,
            args=[],
            default=DefaultSubparser(x=1, bc=DefaultHTTPServer(y=8)),
        )
        == DefaultSubparser(x=1, bc=DefaultHTTPServer(y=8))
    )

    with pytest.raises(SystemExit):
        tyro.cli(DefaultSubparser, args=["--x", "1", "b", "--bc.z", "3"])
    with pytest.raises(SystemExit):
        tyro.cli(DefaultSubparser, args=["--x", "1", "c", "--bc.y", "3"])


def test_subparser_strip_nested() -> None:
    @dataclasses.dataclass
    class DefaultHTTPServer:
        y: int

    @dataclasses.dataclass
    class DefaultSMTPServer:
        z: int

    @dataclasses.dataclass
    class DefaultSubparser:
        x: int
        # We add [int, str] to the annotation here... this should be ignored.
        bc: Union[int, str, DefaultHTTPServer, DefaultSMTPServer] = 5

    assert (
        tyro.cli(DefaultSubparser, args=["--x", "1", "bc:int", "5"])
        == tyro.cli(DefaultSubparser, args=["--x", "1"])
        == DefaultSubparser(x=1, bc=5)
    )
    assert tyro.cli(
        DefaultSubparser, args=["--x", "1", "bc:str", "five"]
    ) == DefaultSubparser(x=1, bc="five")


def test_with_fancy_types() -> None:
    @dataclasses.dataclass
    class Args:
        y: int

    def main(x: Union[Tuple[int, ...], List[str], Args, Dict[str, int]]) -> Any:
        return x

    assert tyro.cli(main, args="x:tuple-int-ellipsis 1 2 3".split(" ")) == (1, 2, 3)
    assert tyro.cli(main, args="x:list-str 1 2 3".split(" ")) == ["1", "2", "3"]
    assert tyro.cli(main, args="x:args --x.y 5".split(" ")) == Args(5)
    assert tyro.cli(main, args="x:dict-str-int 1 2 3 4".split(" ")) == {"1": 2, "3": 4}
