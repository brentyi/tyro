"""Test ExpandDefaultSubcommandHelp marker."""

from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass, field
from typing import Annotated

import pytest

import tyro
import tyro._strings
from tyro.conf import (
    CascadeSubcommandArgs,
    ExpandDefaultSubcommandHelp,
    OmitSubcommandPrefixes,
    arg,
    subcommand,
)


@dataclass
class RunConfig:
    """run tests"""

    num: int = 5
    groups: Annotated[str, arg(aliases=["-g"])] = "auto"
    verbose: Annotated[bool, arg(aliases=["-v"])] = False


@dataclass
class CompareConfig:
    """compare runs"""

    a: int | str = -2
    b: int | str = -1


@dataclass
class Config:
    command: OmitSubcommandPrefixes[
        Annotated[RunConfig, subcommand("run", prefix_name=False)]
        | Annotated[CompareConfig, subcommand("compare", prefix_name=False)]
    ] = field(default_factory=RunConfig)


def _skip_if_argparse(backend: str) -> None:
    if backend == "argparse":
        pytest.skip("cascade help is tyro-backend only")


def _get_helptext(cli_args: list[str], expand: bool = False) -> str:
    config: tuple[object, ...] = (CascadeSubcommandArgs,)
    if expand:
        config = (CascadeSubcommandArgs, ExpandDefaultSubcommandHelp)
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(Config, args=cli_args, prog="ff", config=config)
    return tyro._strings.strip_ansi_sequences(target.getvalue())


def test_expanded_shows_full_args(backend: str):
    """ExpandDefaultSubcommandHelp shows full help with descriptions."""
    _skip_if_argparse(backend)
    helptext = _get_helptext(["--help"], expand=True)

    assert "--num" in helptext
    assert "(default: 5)" in helptext
    assert "--groups" in helptext
    assert "-g" in helptext
    assert "default subcommand options" not in helptext


def test_expanded_still_shows_subcommands(backend: str):
    """Subcommands box is still present with expanded help."""
    _skip_if_argparse(backend)
    helptext = _get_helptext(["--help"], expand=True)

    assert "run" in helptext
    assert "compare" in helptext


def test_condensed_default_preserved(backend: str):
    """Without the marker, condensed panel is shown (backward compat)."""
    _skip_if_argparse(backend)
    helptext = _get_helptext(["--help"], expand=False)

    assert "default subcommand options" in helptext
    assert "(default: 5)" not in helptext
