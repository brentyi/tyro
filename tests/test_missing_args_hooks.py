# mypy: ignore-errors
"""Tests for the experimental tyro.hooks namespace: on_missing_args /
on_missing_subcommand."""

import contextlib
import dataclasses
import io
from typing import List, Union

import pytest

import tyro


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
def _require_native_backend(backend):
    # The hooks are implemented for the default ("tyro") backend only; the
    # argparse backend reports missing arguments from within the vendored
    # argparse internals, where no comparable structured payload exists.
    if backend != "tyro":
        pytest.skip("hooks are implemented for the native backend only")


def test_missing_required_args_hook_receives_args() -> None:
    received: List[list] = []

    def hook(event: tyro.hooks.MissingArgsEvent) -> None:
        received.append(
            [a.arg.lowered.name_or_flags[-1] for a in event.missing_arguments]
        )
        # Already-parsed values are available in the partial output.
        assert event.partial_output["name"] == ["custom"]
        assert event.prog  # Non-empty program path.

    # Nested `with` for Python 3.8 compatibility (no parenthesized form).
    with tyro.hooks.on_missing_args(hook):
        with pytest.raises(SystemExit) as excinfo:
            with contextlib.redirect_stderr(io.StringIO()):
                tyro.cli(Config, args=["--name", "custom"])
    assert excinfo.value.code == 2
    assert received == [["--token", "--number"]]


def test_missing_required_args_hook_may_take_over() -> None:
    class Recovered(Exception):
        pass

    def hook(event: tyro.hooks.MissingArgsEvent) -> None:
        raise Recovered

    stderr = io.StringIO()
    with tyro.hooks.on_missing_args(hook):
        with pytest.raises(Recovered):
            with contextlib.redirect_stderr(stderr):
                tyro.cli(Config, args=[])
    # The hook took over: no error message was printed.
    assert stderr.getvalue() == ""


def test_missing_subcommand_hook_receives_spec() -> None:
    received = []

    def hook(event: tyro.hooks.MissingSubcommandEvent) -> None:
        received.append(sorted(event.subcommand_spec.parser_from_name.keys()))

    with tyro.hooks.on_missing_subcommand(hook):
        with pytest.raises(SystemExit) as excinfo:
            with contextlib.redirect_stderr(io.StringIO()):
                tyro.cli(Union[CommandA, CommandB], args=[])
    assert excinfo.value.code == 2
    assert received == [["command-a", "command-b"]]


def test_missing_required_args_hook_in_subcommand() -> None:
    received: List[list] = []

    def hook(event: tyro.hooks.MissingArgsEvent) -> None:
        received.append(
            [a.arg.lowered.name_or_flags[-1] for a in event.missing_arguments]
        )

    with tyro.hooks.on_missing_args(hook):
        with pytest.raises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                tyro.cli(Union[CommandA, CommandB], args=["command-b", "--flag"])
    assert received == [["--b"]]


def test_hooks_inactive_by_default() -> None:
    stderr = io.StringIO()
    with pytest.raises(SystemExit) as excinfo:
        with contextlib.redirect_stderr(stderr):
            tyro.cli(Config, args=[])
    assert excinfo.value.code == 2
    assert "token" in stderr.getvalue()


def test_hook_does_not_leak_past_context() -> None:
    """The ContextVar-backed hook is restored when the `with` block exits, so a
    later parse does not see it."""
    calls: List[tyro.hooks.MissingArgsEvent] = []

    with tyro.hooks.on_missing_args(calls.append):
        with pytest.raises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                tyro.cli(Config, args=[])
    assert len(calls) == 1

    # Outside the context manager the hook is no longer registered.
    with pytest.raises(SystemExit):
        with contextlib.redirect_stderr(io.StringIO()):
            tyro.cli(Config, args=[])
    assert len(calls) == 1


def test_nested_hooks_restore_outer_on_exit() -> None:
    """An inner context temporarily overrides the outer hook, which is restored
    when the inner block exits."""
    order: List[str] = []

    def outer(event: tyro.hooks.MissingArgsEvent) -> None:
        order.append("outer")

    def inner(event: tyro.hooks.MissingArgsEvent) -> None:
        order.append("inner")

    with tyro.hooks.on_missing_args(outer):
        with tyro.hooks.on_missing_args(inner):
            with pytest.raises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    tyro.cli(Config, args=[])
        # Back to the outer hook.
        with pytest.raises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                tyro.cli(Config, args=[])
    assert order == ["inner", "outer"]
