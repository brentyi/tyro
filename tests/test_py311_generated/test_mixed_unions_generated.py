"""Tests for unsupported union types.

Unions like `int | str` or `SomeDataclassA | SomeDataclassB` are generally OK (note that
the latter will produce a pair of subcommands), but when we write things like
`int | SomeDataclassA` handling gets more complicated; see docstring for
`narrow_union_type()` in _resolvers.py.

Hopefully we can fix/improve this in the future!
"""


import dataclasses
from typing import Union

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
        # Note that we add [int, str] to the annotation here... this should be ignored.
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
        # Note that we add [int, str] to the annotation here... this should be ignored.
        bc: Union[int, str, DefaultHTTPServer, DefaultSMTPServer] = 5

    assert (
        tyro.cli(DefaultSubparser, args=["--x", "1", "--bc", "5"])
        == tyro.cli(DefaultSubparser, args=["--x", "1"])
        == DefaultSubparser(x=1, bc=5)
    )
    assert tyro.cli(
        DefaultSubparser, args=["--x", "1", "--bc", "five"]
    ) == DefaultSubparser(x=1, bc="five")
