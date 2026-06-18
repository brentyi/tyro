"""Experimental hooks for intercepting tyro parse failures.

These let an application that embeds :func:`tyro.cli` observe — and optionally
recover from — the moment parsing is about to fail because required input is
missing. The motivating use case is prompting the user interactively for a
missing value instead of exiting.

Hooks are registered with context managers and backed by
:class:`contextvars.ContextVar`, so they are scoped to the ``with`` block, never
leak into unrelated :func:`tyro.cli` calls, and behave correctly across threads
and :mod:`asyncio` tasks::

    def prompt(event: tyro.hooks.MissingArgsEvent) -> None:
        names = [arg.arg.display_name() for arg in event.missing_arguments]
        print(f"Missing: {', '.join(names)}")

    with tyro.hooks.on_missing_args(prompt):
        config = tyro.cli(Config)

A hook is called just before tyro prints its error and raises ``SystemExit(2)``.
If the hook returns normally, that standard error path still runs. A hook may
instead raise its own exception to take over error handling entirely (e.g. after
gathering the missing values and re-dispatching).

Everything in this module is experimental and may change or be removed in future
versions. Hooks are honored by the default ("tyro") backend only; the argparse
backend reports missing input from within vendored argparse internals, where no
comparable structured payload is available.
"""

from __future__ import annotations

import contextlib
import dataclasses
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional

from typing_extensions import Protocol

if TYPE_CHECKING:
    from ._parsers import ArgWithContext, SubparsersSpecification

__all__ = [
    "MissingArgsEvent",
    "MissingSubcommandEvent",
    "MissingArgsHook",
    "MissingSubcommandHook",
    "on_missing_args",
    "on_missing_subcommand",
]


@dataclasses.dataclass(frozen=True)
class MissingArgsEvent:
    """Payload passed to a :data:`MissingArgsHook`.

    Describes a set of required arguments that were not provided on the command
    line, in the context of a single (sub)parser.
    """

    missing_arguments: List["ArgWithContext"]
    """The required arguments that were not provided. Each
    :class:`tyro._parsers.ArgWithContext` exposes the underlying
    ``ArgumentDefinition`` (via ``.arg``) along with the parser it belongs to."""

    partial_output: Dict[str, Any]
    """Values parsed so far, keyed by prefixed (internal) field name. Arguments
    in :attr:`missing_arguments` are absent from this mapping. Treat it as
    read-only; it is the same dict tyro will continue building from."""

    prog: str
    """The program / subcommand invocation path being parsed, as it appears in
    usage strings (e.g. ``"prog command-b"``). Useful for prompts and messages."""


@dataclasses.dataclass(frozen=True)
class MissingSubcommandEvent:
    """Payload passed to a :data:`MissingSubcommandHook`.

    Describes a required subcommand group for which no subcommand was selected.
    """

    subcommand_spec: "SubparsersSpecification"
    """The unresolved subparser group. ``subcommand_spec.parser_from_name`` maps
    each available subcommand name to its parser specification."""

    partial_output: Dict[str, Any]
    """Values parsed so far, keyed by prefixed (internal) field name. Treat it as
    read-only."""

    prog: str
    """The program / subcommand invocation path being parsed, as it appears in
    usage strings."""


class MissingArgsHook(Protocol):
    """Callable invoked with a :class:`MissingArgsEvent` when required arguments
    are missing. Return ``None`` to let tyro's standard error path proceed, or
    raise to take over."""

    def __call__(self, event: MissingArgsEvent, /) -> None: ...


class MissingSubcommandHook(Protocol):
    """Callable invoked with a :class:`MissingSubcommandEvent` when a required
    subcommand is missing. Return ``None`` to let tyro's standard error path
    proceed, or raise to take over."""

    def __call__(self, event: MissingSubcommandEvent, /) -> None: ...


_missing_args_hook: ContextVar[Optional[MissingArgsHook]] = ContextVar(
    "tyro_missing_args_hook", default=None
)
_missing_subcommand_hook: ContextVar[Optional[MissingSubcommandHook]] = ContextVar(
    "tyro_missing_subcommand_hook", default=None
)


@contextlib.contextmanager
def on_missing_args(hook: MissingArgsHook) -> Iterator[None]:
    """Register `hook` to fire when required arguments are missing.

    The hook is active only for the duration of the ``with`` block and is
    restored to any previously-registered hook on exit (including when an
    exception propagates out).

    Args:
        hook: Called with a :class:`MissingArgsEvent` just before tyro reports
            the missing arguments and raises ``SystemExit(2)``.
    """
    token = _missing_args_hook.set(hook)
    try:
        yield
    finally:
        _missing_args_hook.reset(token)


@contextlib.contextmanager
def on_missing_subcommand(hook: MissingSubcommandHook) -> Iterator[None]:
    """Register `hook` to fire when a required subcommand is missing.

    The hook is active only for the duration of the ``with`` block and is
    restored to any previously-registered hook on exit (including when an
    exception propagates out).

    Args:
        hook: Called with a :class:`MissingSubcommandEvent` just before tyro
            reports the missing subcommand and raises ``SystemExit(2)``.
    """
    token = _missing_subcommand_hook.set(hook)
    try:
        yield
    finally:
        _missing_subcommand_hook.reset(token)


def _get_missing_args_hook() -> Optional[MissingArgsHook]:
    """Internal: return the currently-registered missing-args hook, if any."""
    return _missing_args_hook.get()


def _get_missing_subcommand_hook() -> Optional[MissingSubcommandHook]:
    """Internal: return the currently-registered missing-subcommand hook, if any."""
    return _missing_subcommand_hook.get()
