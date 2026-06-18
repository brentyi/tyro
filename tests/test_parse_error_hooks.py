# mypy: ignore-errors
"""Tests for the private tyro._errors namespace: the unified on_parse_error hook
and its ParseErrorEvent subclasses, one per parse-failure category."""

# NOTE: deliberately NOT using `from __future__ import annotations` -- several
# tests below annotate tyro-parsed callables with closure-local types (e.g.
# mutex `Group`s defined inside the test function), which tyro resolves at
# runtime via get_type_hints; stringized annotations would fail to resolve them.

import contextlib
import dataclasses
import io
from typing import TYPE_CHECKING, List, Tuple, Union

import pytest
from typing_extensions import Annotated

import tyro
from tyro import _errors

if TYPE_CHECKING:
    from tyro._arguments import ArgumentDefinition


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
    # argparse backend reports failures from within the vendored argparse
    # internals, where no comparable structured payload exists.
    if backend != "tyro":
        pytest.skip("hooks are implemented for the native backend only")


@contextlib.contextmanager
def _capture(hook):
    """Register `hook` and swallow stderr for the enclosed parse."""
    with _errors.on_parse_error(hook):
        with contextlib.redirect_stderr(io.StringIO()):
            yield


def _run_expecting_exit(hook, cls_or_fn, args) -> None:
    with _capture(hook):
        with pytest.raises(SystemExit) as excinfo:
            tyro.cli(cls_or_fn, args=args)
    assert excinfo.value.code == 2


# ---------------------------------------------------------------------------
# One test per event category: the right subclass fires with the right payload.
# ---------------------------------------------------------------------------


def test_missing_args() -> None:
    seen: List[_errors.MissingArgs] = []
    _run_expecting_exit(seen.append, Config, ["--name", "custom"])
    (event,) = seen
    assert isinstance(event, _errors.MissingArgs)
    names = sorted(a.arg.lowered.name_or_flags[-1] for a in event.missing_arguments)
    assert names == ["--number", "--token"]
    # partial_output is raw/pre-conversion: already-parsed values are token lists.
    assert event.partial_output["name"] == ["custom"]
    assert event.prog


def test_missing_mutex_group() -> None:
    RequiredGroup = tyro.conf.create_mutex_group(required=True)

    def main(
        option_a: Annotated[Union[str, None], RequiredGroup] = None,
        option_b: Annotated[Union[int, None], RequiredGroup] = None,
    ) -> None:
        del option_a, option_b

    seen: List[_errors.MissingMutexGroup] = []
    _run_expecting_exit(seen.append, main, [])
    (event,) = seen
    assert isinstance(event, _errors.MissingMutexGroup)
    # One unsatisfied group, with both members reported.
    (group,) = event.groups
    names = sorted(a.arg.lowered.name_or_flags[-1] for a in group)
    assert names == ["--option-a", "--option-b"]


def test_missing_subcommand() -> None:
    seen: List[_errors.MissingSubcommand] = []
    _run_expecting_exit(seen.append, Union[CommandA, CommandB], [])
    (event,) = seen
    assert isinstance(event, _errors.MissingSubcommand)
    assert sorted(event.subcommand_spec.parser_from_name.keys()) == [
        "command-a",
        "command-b",
    ]


def test_mutex_conflict() -> None:
    Group = tyro.conf.create_mutex_group(required=False)

    def main(
        option_a: Annotated[Union[str, None], Group] = None,
        option_b: Annotated[Union[int, None], Group] = None,
    ) -> None:
        del option_a, option_b

    seen: List[_errors.MutexConflict] = []
    _run_expecting_exit(seen.append, main, ["--option-a", "x", "--option-b", "3"])
    (event,) = seen
    assert isinstance(event, _errors.MutexConflict)
    assert event.first is not event.second
    assert event.first_token and event.second_token


def test_bad_value_too_few() -> None:
    # A fixed-arity argument given too few values fires BadValue.
    @dataclasses.dataclass
    class WithPair:
        xy: Tuple[int, int]

    seen: List[_errors.BadValue] = []
    _run_expecting_exit(seen.append, WithPair, ["--xy", "1"])
    (event,) = seen
    assert isinstance(event, _errors.BadValue)
    assert event.reason == "too_few_values"
    assert event.offending_value is None
    assert event.argument is not None


# NOTE: two narrow categories -- SubcommandConflict (requires a flag belonging
# to a default subcommand implicitly selecting it, then an explicit conflicting
# selection) and BadValue(reason="fixed") (the "fixed argument cannot accept a
# value" path) -- are wired in the backend but not currently reachable through a
# stable public-facing tyro.cli invocation we can pin a test to. They are
# covered structurally below (construction + the unified contract) so that the
# event surface stays consistent; if a stable trigger is found, replace these
# with true integration tests.


def _capture_one_argument() -> "ArgumentDefinition":
    """Grab a real ArgumentDefinition from a triggered BadValue event, so the
    structural test can construct events with a genuine argument rather than a
    fabricated None (argument is non-Optional and always populated at runtime)."""
    captured: List[_errors.BadValue] = []

    @dataclasses.dataclass
    class WithPair:
        xy: Tuple[int, int]

    with _capture(captured.append):
        with pytest.raises(SystemExit):
            tyro.cli(WithPair, args=["--xy", "1"])
    return captured[0].argument


def test_structural_event_construction() -> None:
    """Every event type is a ParseErrorEvent and carries its declared fields.

    Guards the parts of the surface (SubcommandConflict, BadValue 'fixed') that
    lack a stable end-to-end trigger today, and pins the field contract for all.
    """
    conflict = _errors.SubcommandConflict(
        prog="p",
        attempted="b",
        already_selected="a",
        trigger_flag="--a.x",
        is_same_subcommand=False,
    )
    assert isinstance(conflict, _errors.ParseErrorEvent)
    assert conflict.attempted == "b" and conflict.already_selected == "a"

    fixed = _errors.BadValue(
        prog="p",
        argument=_capture_one_argument(),
        reason="fixed",
        offending_value="5",
    )
    assert isinstance(fixed, _errors.ParseErrorEvent)
    assert fixed.reason == "fixed" and fixed.offending_value == "5"
    assert fixed.argument is not None


def test_invalid_choice() -> None:
    from typing import Literal

    @dataclasses.dataclass
    class WithChoice:
        mode: Literal["a", "b", "c"] = "a"

    seen: List[_errors.InvalidChoice] = []
    _run_expecting_exit(seen.append, WithChoice, ["--mode", "z"])
    (event,) = seen
    assert isinstance(event, _errors.InvalidChoice)
    assert event.value == "z"
    assert set(event.choices) == {"a", "b", "c"}


def test_unrecognized_args() -> None:
    seen: List[_errors.UnrecognizedArgs] = []
    _run_expecting_exit(
        seen.append, Config, ["--token", "t", "--number", "1", "--bogus", "x"]
    )
    (event,) = seen
    assert isinstance(event, _errors.UnrecognizedArgs)
    assert any("bogus" in tok for tok in event.tokens)


def test_instantiation_failure() -> None:
    # A value that parses as a token but fails type conversion (int("x")
    # raises ValueError) goes through the per-argument cast path, which tyro
    # wraps as an InstantiationError -> InstantiationFailure event.
    @dataclasses.dataclass
    class Config2:
        value: int

    seen: List[_errors.InstantiationFailure] = []
    _run_expecting_exit(seen.append, Config2, ["--value", "notanint"])
    (event,) = seen
    assert isinstance(event, _errors.InstantiationFailure)
    assert event.message
    # The failure is attributed to the offending argument.
    assert event.argument is not None


# ---------------------------------------------------------------------------
# Cross-cutting behaviors of the unified hook.
# ---------------------------------------------------------------------------


def test_hook_may_take_over_by_raising() -> None:
    class Recovered(Exception):
        pass

    def hook(event: _errors.ParseErrorEvent) -> None:
        raise Recovered

    stderr = io.StringIO()
    with _errors.on_parse_error(hook):
        with pytest.raises(Recovered):
            with contextlib.redirect_stderr(stderr):
                tyro.cli(Config, args=[])
    # The hook took over: no standard error message was printed.
    assert stderr.getvalue() == ""


def test_unhandled_event_falls_through() -> None:
    """A hook that ignores an event lets tyro's normal error proceed."""
    calls: List[_errors.ParseErrorEvent] = []

    def hook(event: _errors.ParseErrorEvent) -> None:
        calls.append(event)
        # Deliberately handle nothing; return None.

    stderr = io.StringIO()
    with _errors.on_parse_error(hook):
        with pytest.raises(SystemExit):
            with contextlib.redirect_stderr(stderr):
                tyro.cli(Config, args=[])
    assert len(calls) == 1
    # Standard error output still happened.
    assert "token" in stderr.getvalue().lower() or stderr.getvalue() != ""


def test_partial_output_is_a_copy() -> None:
    """The hook receives a shallow copy; mutating it cannot perturb parsing."""

    def hook(event: _errors.ParseErrorEvent) -> None:
        if isinstance(event, _errors.MissingArgs):
            event.partial_output.clear()
            event.partial_output["injected"] = "value"

    with _capture(hook):
        with pytest.raises(SystemExit):
            tyro.cli(Config, args=["--name", "custom"])

    # A subsequent successful parse is unaffected by the earlier mutation.
    with _errors.on_parse_error(hook):
        result = tyro.cli(
            Config, args=["--token", "t", "--number", "1", "--name", "custom"]
        )
    assert result.name == "custom"


def test_errors_inactive_by_default() -> None:
    stderr = io.StringIO()
    with pytest.raises(SystemExit) as excinfo:
        with contextlib.redirect_stderr(stderr):
            tyro.cli(Config, args=[])
    assert excinfo.value.code == 2
    assert "token" in stderr.getvalue()


def test_hook_does_not_leak_past_context() -> None:
    """The ContextVar-backed hook is restored when the `with` block exits."""
    calls: List[_errors.ParseErrorEvent] = []

    with _capture(calls.append):
        with pytest.raises(SystemExit):
            tyro.cli(Config, args=[])
    assert len(calls) == 1

    # Outside the context manager the hook is no longer registered.
    with pytest.raises(SystemExit):
        with contextlib.redirect_stderr(io.StringIO()):
            tyro.cli(Config, args=[])
    assert len(calls) == 1


def test_nested_errors_restore_outer_on_exit() -> None:
    """An inner context temporarily overrides the outer hook, then restores it."""
    order: List[str] = []

    with _errors.on_parse_error(lambda e: order.append("outer")):
        with _errors.on_parse_error(lambda e: order.append("inner")):
            with pytest.raises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    tyro.cli(Config, args=[])
        with pytest.raises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                tyro.cli(Config, args=[])
    assert order == ["inner", "outer"]


def test_missing_args_in_subcommand() -> None:
    """Missing args inside a selected subcommand fire with that subcommand's
    prog path."""
    seen: List[_errors.MissingArgs] = []

    def hook(event: _errors.ParseErrorEvent) -> None:
        if isinstance(event, _errors.MissingArgs):
            seen.append(event)

    with _capture(hook):
        with pytest.raises(SystemExit):
            tyro.cli(Union[CommandA, CommandB], args=["command-b", "--flag"])
    (event,) = seen
    names = [a.arg.lowered.name_or_flags[-1] for a in event.missing_arguments]
    assert names == ["--b"]
