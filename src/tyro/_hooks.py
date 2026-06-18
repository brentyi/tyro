"""Internal, unstable hooks for intercepting tyro parse failures.

.. warning::

    **This module is private and experimental.** It is named ``_hooks`` (leading
    underscore) deliberately: it is **not** part of tyro's public, stable API.
    Everything here — the event classes, their fields, the registration function,
    and notably the *internal tyro types exposed on the event payloads*
    (:class:`tyro._parsers.ArgWithContext`,
    :class:`tyro._arguments.ArgumentDefinition`,
    :class:`tyro._parsers.SubparsersSpecification`, and the raw ``partial_output``
    dictionaries) — may change or be removed in **any** release, without notice
    or a deprecation period. Pin an exact tyro version if you depend on it.

What this is
------------
A single hook, :func:`on_parse_error`, that fires whenever :func:`tyro.cli` is
about to reject the user's command-line input. "About to reject" covers the whole
failure surface: missing required input, conflicts, bad/invalid values,
unrecognized arguments, and — from the user's point of view, still a way their
input was rejected — failures constructing the final object from parsed values.

The hook receives one :class:`ParseErrorEvent`. Its concrete runtime type is one
of the subclasses below; match the ones you care about with ``isinstance`` and
ignore the rest::

    def handle(event: tyro._hooks.ParseErrorEvent) -> None:
        if isinstance(event, tyro._hooks.MissingArgs):
            names = [a.arg.display_name() for a in event.missing_arguments]
            print(f"Missing: {', '.join(names)}")
        # Any event type not handled here simply falls through to tyro's
        # standard error output.

    with tyro._hooks.on_parse_error(handle):
        config = tyro.cli(Config)

Forward-compatibility contract
------------------------------
New :class:`ParseErrorEvent` subclasses may be introduced in any release. A hook
**must tolerate receiving a subclass it does not recognize** — match the cases
you care about and let the rest fall through (return ``None``). Do **not** write
an exhaustive ``else: assert_never(event)`` over the hierarchy; that would turn
every newly-added category into a breaking change for your code.

What a hook can do
------------------
A hook is called just before tyro prints its error and raises ``SystemExit(2)``.
It has exactly two levers:

- **Return** ``None`` to let tyro's standard error path proceed (print the error,
  then exit). Right for logging, telemetry, or custom diagnostics. A hook cannot
  "fill in" the missing/invalid input by mutating the event — the failure has
  already been decided and (for parse-time events) no type conversion has run
  yet. The payloads are read-only snapshots; ``partial_output`` is a copy.
- **Raise** to take over error handling entirely. This is how interactive
  recovery is built: gather the needed input (e.g. by prompting), raise, and let
  the surrounding application catch that and re-invoke :func:`tyro.cli` with
  corrected arguments. Recovery is therefore *raise-and-re-dispatch*, not
  in-place resumption. Only the first failing parser level surfaces before the
  exit, so a single re-dispatch may surface a further round of errors.

Re-entrancy
-----------
The hook stays registered for the whole ``with`` block. Prefer re-dispatching
:func:`tyro.cli` *outside* the block (after catching the hook's exception). If
you call :func:`tyro.cli` from *within* the hook and that call hits another
failure, the hook fires again — which can recurse. Guard against this yourself
if you need it.

Concurrency
-----------
Registration is backed by :class:`contextvars.ContextVar`, so concurrent
:func:`tyro.cli` calls never see each other's hooks. Standard contextvars
semantics apply: an :mod:`asyncio` task started inside the ``with`` block
inherits the registration; a raw :class:`threading.Thread` you spawn does not.

Backend support
---------------
Hooks are honored by the default ("tyro") backend only. The argparse backend
reports failures from within vendored argparse internals, where no comparable
structured payload is available.
"""

from __future__ import annotations

import contextlib
import dataclasses
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional, Tuple

from typing_extensions import Protocol

if TYPE_CHECKING:
    from ._arguments import ArgumentDefinition
    from ._parsers import ArgWithContext, SubparsersSpecification

__all__ = [
    # Base + concrete events.
    "ParseErrorEvent",
    "MissingArgs",
    "MissingMutexGroup",
    "MissingSubcommand",
    "MutexConflict",
    "SubcommandConflict",
    "BadValue",
    "InvalidChoice",
    "UnrecognizedArgs",
    "InstantiationFailure",
    # Hook protocol + registration.
    "ParseErrorHook",
    "on_parse_error",
]


# ---------------------------------------------------------------------------
# Event hierarchy.
#
# `ParseErrorEvent` is the base that hooks annotate against. Each concrete
# subclass carries exactly the context available at its originating failure
# site -- there is intentionally no uniform payload, because the information
# differs per category. Fields typed with internal tyro classes are exposed
# as-is; see the module-level warning.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ParseErrorEvent:
    """Base class for every parse-failure event.

    Hooks should annotate their parameter as ``ParseErrorEvent`` and narrow with
    ``isinstance`` to the concrete subclasses they handle. New subclasses may be
    added in future releases (see the module-level forward-compatibility note),
    so always allow unrecognized events to fall through.

    Only the fields truly shared by *all* failures live here. Anything
    category-specific (including ``partial_output``, which is only meaningful
    where parsing got far enough to accumulate state) lives on the subclasses.
    """

    prog: str
    """The program / subcommand invocation path being parsed, as it appears in
    usage strings (e.g. ``"prog command-b"``). Useful for prompts and messages."""


# -- "Missing input" events. These occur during the final missing-argument
#    sweep, so a partial parse state has accumulated and is worth exposing. --


@dataclasses.dataclass(frozen=True)
class MissingArgs(ParseErrorEvent):
    """One or more required arguments were not provided."""

    missing_arguments: List["ArgWithContext"]
    """The required arguments that were not provided. Each
    :class:`tyro._parsers.ArgWithContext` exposes the underlying
    ``ArgumentDefinition`` via ``.arg``. (Internal type; see module warning.)"""

    partial_output: Dict[str, Any]
    """Low-level escape hatch: tyro's *raw, pre-conversion* parse state. Keys are
    intern-prefixed dotted destinations (``"inner.x"``); values are raw string
    tokens (``['5']``, not ``5``); unprovided fields are present with a
    ``tyro.MISSING`` sentinel. A shallow copy -- mutating it does nothing.
    Prefer :attr:`missing_arguments`. (Internal format; see module warning.)"""


@dataclasses.dataclass(frozen=True)
class MissingMutexGroup(ParseErrorEvent):
    """One or more required mutually-exclusive groups had no member selected."""

    groups: List[List["ArgWithContext"]]
    """Each unsatisfied required group, as the list of its member arguments. Any
    single member would have satisfied its group. (Internal type; see warning.)"""

    partial_output: Dict[str, Any]
    """Raw, pre-conversion parse state; see :attr:`MissingArgs.partial_output`."""


@dataclasses.dataclass(frozen=True)
class MissingSubcommand(ParseErrorEvent):
    """A required subcommand group had no subcommand selected."""

    subcommand_spec: "SubparsersSpecification"
    """The unresolved subparser group; ``subcommand_spec.parser_from_name`` maps
    each available subcommand name to its parser. (Internal type; see warning.)"""

    partial_output: Dict[str, Any]
    """Raw, pre-conversion parse state; see :attr:`MissingArgs.partial_output`."""


# -- "Conflict" events. These fire mid-parse, before a full output dict exists,
#    so they carry only the specific arguments / names in conflict. --


@dataclasses.dataclass(frozen=True)
class MutexConflict(ParseErrorEvent):
    """Two arguments from the same mutually-exclusive group were both given."""

    first: "ArgumentDefinition"
    """The argument that was seen first. (Internal type; see module warning.)"""

    second: "ArgumentDefinition"
    """The conflicting argument seen afterwards. (Internal type; see warning.)"""

    first_token: str
    """The command-line spelling that selected :attr:`first` (e.g. ``"--a"``)."""

    second_token: str
    """The command-line spelling that selected :attr:`second`."""


@dataclasses.dataclass(frozen=True)
class SubcommandConflict(ParseErrorEvent):
    """An explicit subcommand selection conflicts with one already chosen
    implicitly by a flag belonging to a default subcommand."""

    attempted: str
    """The subcommand the user tried to select explicitly."""

    already_selected: str
    """The subcommand that was already implicitly selected."""

    trigger_flag: str
    """The flag whose use implicitly selected :attr:`already_selected`."""

    is_same_subcommand: bool
    """``True`` if the user re-selected the already-selected subcommand (a
    redundant selection); ``False`` if they tried to select a different one."""


# -- "Bad value" events. These fire mid-parse for a single argument. --


@dataclasses.dataclass(frozen=True)
class BadValue(ParseErrorEvent):
    """An argument was given a value it cannot accept, or too few values."""

    argument: "ArgumentDefinition"
    """The offending argument. (Internal type; see module warning.)"""

    reason: str
    """Why the value was rejected. One of ``"fixed"`` (a fixed argument cannot
    accept any value) or ``"too_few_values"`` (a fixed-arity argument did not get
    all the values it requires). Treat unknown values as "some bad value"."""

    offending_value: Optional[str]
    """The unexpected token, when there is one (``reason == "fixed"``); ``None``
    when the problem is absence of a value (``reason == "too_few_values"``)."""


@dataclasses.dataclass(frozen=True)
class InvalidChoice(ParseErrorEvent):
    """A value was not among an argument's allowed choices."""

    argument: "ArgumentDefinition"
    """The argument with a constrained choice set. (Internal type; see warning.)"""

    value: str
    """The provided value that was not a valid choice."""

    choices: Tuple[str, ...]
    """The allowed choices, in declaration order."""


# -- "Unrecognized input" event. --


@dataclasses.dataclass(frozen=True)
class UnrecognizedArgs(ParseErrorEvent):
    """One or more command-line tokens were not recognized."""

    tokens: List[str]
    """The unrecognized command-line tokens, in the order encountered."""


# -- Post-parse construction failure. Surfaced to the user as just another way
#    their input was rejected, even though it happens after token parsing. --


@dataclasses.dataclass(frozen=True)
class InstantiationFailure(ParseErrorEvent):
    """Parsing succeeded, but constructing the output object from the parsed
    values failed (e.g. a field constructor raised :class:`ValueError`)."""

    message: str
    """The human-readable failure message."""

    argument: Optional["ArgumentDefinition"]
    """The argument whose value triggered the failure, if it could be attributed
    to one; ``None`` otherwise. (Internal type; see module warning.)"""


# ---------------------------------------------------------------------------
# Hook protocol + registration.
# ---------------------------------------------------------------------------


class ParseErrorHook(Protocol):
    """Callable invoked with a :class:`ParseErrorEvent` just before tyro reports
    a parse failure and raises ``SystemExit(2)``. Return ``None`` to let tyro's
    standard error path proceed, or raise to take over."""

    def __call__(self, event: ParseErrorEvent, /) -> None: ...


_parse_error_hook: ContextVar[Optional[ParseErrorHook]] = ContextVar(
    "tyro_parse_error_hook", default=None
)


@contextlib.contextmanager
def on_parse_error(hook: ParseErrorHook) -> Iterator[None]:
    """Register ``hook`` to fire whenever tyro is about to reject parsed input.

    The hook is active only for the duration of the ``with`` block and is
    restored to any previously-registered hook on exit (including when an
    exception propagates out). See the module docstring for the full contract.

    Args:
        hook: Called with a :class:`ParseErrorEvent` (one of its concrete
            subclasses) just before tyro reports the failure and exits.
    """
    token = _parse_error_hook.set(hook)
    try:
        yield
    finally:
        _parse_error_hook.reset(token)


def _has_hook() -> bool:
    """Internal: whether any parse-error hook is currently registered.

    Fire sites use this to skip building an event (and copying parse state) on
    the common no-hook path, since that work would otherwise be discarded by
    :func:`_fire`.
    """
    return _parse_error_hook.get() is not None


def _fire(event: ParseErrorEvent) -> None:
    """Internal: invoke the registered parse-error hook with ``event``, if any.

    Called at each failure site just before the standard error-and-exit path. If
    the hook raises, that exception propagates and takes over error handling; if
    it returns, the caller proceeds to print and exit as usual.
    """
    hook = _parse_error_hook.get()
    if hook is not None:
        hook(event)
