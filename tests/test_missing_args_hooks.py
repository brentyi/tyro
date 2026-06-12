# mypy: ignore-errors
"""Tests for the experimental missing_required_args_hook / missing_subcommand_hook."""

import contextlib
import dataclasses
import io
from typing import List, Union

import pytest

import tyro
from tyro import _settings


@dataclasses.dataclass
class Config:
    token: str
    number: int
    name: str = "default"


@dataclasses.dataclass
class CommandA:
    a: int = 0


@dataclasses.dataclass
class CommandB:
    b: str
    flag: bool = False


@pytest.fixture(autouse=True)
def _reset_hooks(backend):
    # The hooks are implemented for the default ("tyro") backend only; the
    # argparse backend reports missing arguments from within the vendored
    # argparse internals, where no comparable structured payload exists.
    if backend != "tyro":
        pytest.skip("hooks are implemented for the native backend only")
    yield
    _settings.missing_required_args_hook = None
    _settings.missing_subcommand_hook = None


def test_missing_required_args_hook_receives_args() -> None:
    received: List[list] = []

    def hook(missing_args, output) -> None:
        received.append([a.arg.lowered.name_or_flags[-1] for a in missing_args])
        # Already-parsed values are available in the partial output.
        assert output["name"] == ["custom"]

    _settings.missing_required_args_hook = hook
    # Nested `with` for Python 3.8 compatibility (no parenthesized form).
    with pytest.raises(SystemExit) as excinfo:
        with contextlib.redirect_stderr(io.StringIO()):
            tyro.cli(Config, args=["--name", "custom"])
    assert excinfo.value.code == 2
    assert received == [["--token", "--number"]]


def test_missing_required_args_hook_may_take_over() -> None:
    class Recovered(Exception):
        pass

    def hook(missing_args, output) -> None:
        raise Recovered

    _settings.missing_required_args_hook = hook
    stderr = io.StringIO()
    with pytest.raises(Recovered), contextlib.redirect_stderr(stderr):
        tyro.cli(Config, args=[])
    # The hook took over: no error message was printed.
    assert stderr.getvalue() == ""


def test_missing_subcommand_hook_receives_spec() -> None:
    received = []

    def hook(subparser_spec, output) -> None:
        received.append(sorted(subparser_spec.parser_from_name.keys()))

    _settings.missing_subcommand_hook = hook
    # Nested `with` for Python 3.8 compatibility (no parenthesized form).
    with pytest.raises(SystemExit) as excinfo:
        with contextlib.redirect_stderr(io.StringIO()):
            tyro.cli(Union[CommandA, CommandB], args=[])
    assert excinfo.value.code == 2
    assert received == [["command-a", "command-b"]]


def test_missing_required_args_hook_in_subcommand() -> None:
    received: List[list] = []

    def hook(missing_args, output) -> None:
        received.append([a.arg.lowered.name_or_flags[-1] for a in missing_args])

    _settings.missing_required_args_hook = hook
    with pytest.raises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
        tyro.cli(Union[CommandA, CommandB], args=["command-b", "--flag"])
    assert received == [["--b"]]


def test_hooks_inactive_by_default() -> None:
    stderr = io.StringIO()
    with pytest.raises(SystemExit) as excinfo, contextlib.redirect_stderr(stderr):
        tyro.cli(Config, args=[])
    assert excinfo.value.code == 2
    assert "token" in stderr.getvalue()
