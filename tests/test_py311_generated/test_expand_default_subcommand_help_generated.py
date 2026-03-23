"""Test CascadeSubcommandArgs default subcommand help expansion."""

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


def _get_helptext(cli_args: list[str], compact_help: bool = False) -> str:
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(
            Config,
            args=cli_args,
            prog="ff",
            config=(CascadeSubcommandArgs,),
            compact_help=compact_help,
        )
    return tyro._strings.strip_ansi_sequences(target.getvalue())


def test_expanded_shows_full_args(backend: str):
    """Default --help shows full args with descriptions."""
    _skip_if_argparse(backend)
    helptext = _get_helptext(["--help"])

    assert "--num" in helptext
    assert "(default: 5)" in helptext
    assert "--groups" in helptext
    assert "-g" in helptext
    assert "source subcommand:" in helptext


def test_expanded_still_shows_subcommands(backend: str):
    """Subcommands box is still present with expanded help."""
    _skip_if_argparse(backend)
    helptext = _get_helptext(["--help"])

    assert "run" in helptext
    assert "compare" in helptext


def test_condensed_in_compact_mode(backend: str):
    """compact_help=True shows condensed panel."""
    _skip_if_argparse(backend)
    helptext = _get_helptext(["--help"], compact_help=True)

    assert "default subcommand options" in helptext
    assert "(default: 5)" not in helptext


def test_verbose_flag_expands_in_compact_mode(backend: str):
    """In compact_help mode, -H/--help-verbose shows full expanded help."""
    _skip_if_argparse(backend)
    helptext = _get_helptext(["-H"], compact_help=True)

    assert "--num" in helptext
    assert "(default: 5)" in helptext
    assert "source subcommand:" in helptext


@dataclass
class _SubcommandA:
    x: int = 1


@dataclass
class _SubcommandB:
    y: int = 2


@dataclass
class _RegularNested:
    z: int = 99


@dataclass
class _MixedConfig:
    # This is a subcommand with a default — its args get "dataset" extern prefix.
    dataset0: Annotated[
        _SubcommandA | _SubcommandB,
        arg(name="dataset"),
    ] = field(default_factory=_SubcommandA)
    # This is a plain nested struct, also renamed to "dataset" extern prefix.
    # Its args will share the same "dataset options" group.
    dataset1: Annotated[_RegularNested, arg(name="dataset")] = field(
        default_factory=_RegularNested
    )


def test_no_source_label_when_group_has_mixed_args(backend: str):
    """When a group has both default subcommand args and regular args
    (e.g., via extern_prefix renaming), the source label should not appear."""
    _skip_if_argparse(backend)

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(
            _MixedConfig,
            args=["--help"],
            prog="test",
            config=(CascadeSubcommandArgs,),
        )
    helptext = tyro._strings.strip_ansi_sequences(target.getvalue())

    # Both args appear, and the subcommand args get their own labeled group
    # while the regular arg gets a separate unlabeled group.
    assert "--dataset.z" in helptext
    assert "--dataset.x" in helptext
    assert "source subcommand:" in helptext

    # The source label should only appear once (for the subcommand group).
    assert helptext.count("source subcommand:") == 1


@dataclass
class _RequiredArgSub:
    """subcommand with a required arg"""

    required_val: int = tyro.MISSING_NONPROP
    optional_val: int = 10


@dataclass
class _OtherSub:
    """other subcommand"""

    w: int = 0


@dataclass
class _RequiredArgConfig:
    command: OmitSubcommandPrefixes[
        Annotated[_RequiredArgSub, subcommand("req", prefix_name=False)]
        | Annotated[_OtherSub, subcommand("other", prefix_name=False)]
    ] = field(default_factory=_RequiredArgSub)


def test_compact_required_arg_in_default_subcommand(backend: str):
    """compact_help=True shows '(required)' for required args in default subcommand."""
    _skip_if_argparse(backend)
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(
            _RequiredArgConfig,
            args=["--help"],
            prog="test",
            config=(CascadeSubcommandArgs,),
            compact_help=True,
        )
    helptext = tyro._strings.strip_ansi_sequences(target.getvalue())
    assert "(required)" in helptext
    assert "--required-val" in helptext


@dataclass
class _InnerSubA:
    """inner sub A"""

    p: int = 1


@dataclass
class _InnerSubB:
    """inner sub B"""

    q: int = 2


@dataclass
class _OuterSub:
    """outer sub with nested subcommand"""

    val: int = 5
    inner: Annotated[_InnerSubA | _InnerSubB, subcommand(prefix_name=False)] = field(
        default_factory=_InnerSubA
    )


@dataclass
class _OuterOther:
    """other outer sub"""

    r: int = 0


@dataclass
class _NestedSubConfig:
    command: OmitSubcommandPrefixes[
        Annotated[_OuterSub, subcommand("outer", prefix_name=False)]
        | Annotated[_OuterOther, subcommand("other", prefix_name=False)]
    ] = field(default_factory=_OuterSub)


def test_nested_default_subcommand_recursive(backend: str):
    """CascadeSubcommandArgs recurses into nested default subparsers."""
    _skip_if_argparse(backend)
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(
            _NestedSubConfig,
            args=["--help"],
            prog="test",
            config=(CascadeSubcommandArgs,),
        )
    helptext = tyro._strings.strip_ansi_sequences(target.getvalue())
    # The outer default subcommand's arg should appear.
    assert "--val" in helptext
    # The inner default subcommand's arg should also appear via recursion.
    assert "--p INT" in helptext
