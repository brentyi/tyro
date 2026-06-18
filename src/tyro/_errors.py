"""Internal, unstable hooks for intercepting tyro parse failures.

.. warning::

    **This module is private and experimental.** It is named ``_errors`` (leading
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

    def handle(event: tyro._errors.ParseErrorEvent) -> None:
        if isinstance(event, tyro._errors.MissingArgs):
            names = [a.arg.display_name() for a in event.missing_arguments]
            print(f"Missing: {', '.join(names)}")
        # Any event type not handled here simply falls through to tyro's
        # standard error output.

    with tyro._errors.on_parse_error(handle):
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
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterator,
    List,
    NoReturn,
    Optional,
    Tuple,
)

from typing_extensions import Protocol

if TYPE_CHECKING:
    from ._arguments import ArgumentDefinition
    from ._parsers import ArgWithContext, SubparsersSpecification

# No `__all__`: this is a private, underscore-prefixed module, so there is no
# public export surface to declare. The names below are grouped as: the event
# hierarchy (`ParseErrorEvent` + its subclasses), the hook protocol/registration
# (`ParseErrorHook`, `on_parse_error`), and the internal rendering/firing
# helpers (`_render`, `_fire`, `_has_hook`, `_fire_and_exit`).


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

    def _help_progs(self) -> str | list[str]:
        """Program path(s) for the rendered error's "--help" footer. Defaults to
        :attr:`prog`; events spanning multiple (sub)commands override this."""
        return self.prog


# -- "Missing input" events. These occur during the final missing-argument
#    sweep, so a partial parse state has accumulated and is worth exposing. --


@dataclasses.dataclass(frozen=True)
class MissingArgs(ParseErrorEvent):
    """One or more required arguments were not provided."""

    missing_arguments: List["ArgWithContext"]
    """The required arguments that were not provided. Each
    :class:`tyro._parsers.ArgWithContext` exposes the underlying
    ``ArgumentDefinition`` via ``.arg``. (Internal type; see module warning.)"""

    unrecognized_tokens: List[str]
    """Any unrecognized command-line tokens seen alongside the missing arguments.
    Rendered as a trailing "Unrecognized options" block; usually empty."""

    partial_output: Dict[str, Any]
    """Low-level escape hatch: tyro's *raw, pre-conversion* parse state. Keys are
    intern-prefixed dotted destinations (``"inner.x"``); values are raw string
    tokens (``['5']``, not ``5``); unprovided fields are present with a
    ``tyro.MISSING`` sentinel. A shallow copy -- mutating it does nothing.
    Prefer :attr:`missing_arguments`. (Internal format; see module warning.)"""

    def _args_from_prog(self) -> Dict[str, list[Any]]:
        """Group the missing arguments by the (sub)command prog they belong to,
        preserving first-seen order. Used both to render the per-prog "Missing
        from ..." sections and to derive the multi-prog ``--help`` footer."""
        args_from_prog: Dict[str, list[Any]] = {}
        for arg_ctx in self.missing_arguments:
            arg_prog = (
                self.prog
                if arg_ctx.source_parser.prog_suffix == ""
                else f"{self.prog} {arg_ctx.source_parser.prog_suffix}"
            )
            args_from_prog.setdefault(arg_prog, []).append(arg_ctx.arg)
        return args_from_prog

    def _help_progs(self) -> str | list[str]:
        # The footer spans every (sub)command that had a missing argument.
        return list(self._args_from_prog().keys())


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

    found_token: Optional[str]
    """The unexpected token seen where a subcommand was expected, if any (e.g. the
    user passed something that is not one of the available subcommand names);
    ``None`` if no token was present at all."""

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


# ---------------------------------------------------------------------------
# Rendering.
#
# Most events render as a standard box of title + contents via
# `_tyro_help_formatting.error_and_exit`, handled by `_render` here -- one place
# per event type -- so the backend's failure sites collapse to a single
# `_fire_and_exit(event, ...)` call. Two events are NOT handled by `_render`,
# because their rendering is not a static description of the failure; both still
# render in this module so error rendering stays centralized:
#
#   - UnrecognizedArgs: its body is the output of a computed fuzzy-match
#     ("did you mean") engine; it keeps its dedicated renderer
#     `_tyro_help_formatting.unrecognized_args_error`.
#   - InstantiationFailure: it draws a bespoke box that differs from the
#     standard one (non-bold "Value error" title, "For full helptext, see ..."
#     footer), rendered by `fire_and_exit_instantiation_failure` below. It is
#     fired post-parse from `_cli.py`, which only constructs the event.
#
# The event types above are dependency-light, so importing this module is cheap
# (it is pulled in early, before the heavy formatting/argument machinery). The
# rendering helpers below pull in the formatting layer (`_tyro_help_formatting`,
# `_arguments`, `_fmtlib`); those imports are deferred to call time to preserve
# that property. Nothing in those modules imports `_errors`, so this is purely
# about import cost and ordering, not about breaking a cycle.
# ---------------------------------------------------------------------------


def _render(event: ParseErrorEvent) -> tuple[str, list[Any]]:
    """Return ``(title, contents)`` for an event, matching tyro's historical
    message text byte-for-byte. The help footer's program path(s) come from
    ``event._help_progs()`` separately. Raises ``KeyError`` for the events with
    dedicated renderers (``UnrecognizedArgs``, ``InstantiationFailure``)."""
    from . import _fmtlib as fmt
    from . import _singleton

    if isinstance(event, MutexConflict):
        return (
            "Mutually exclusive arguments",
            [
                f"Arguments {event.first_token} and {event.second_token} "
                "are not allowed together!"
            ],
        )

    if isinstance(event, SubcommandConflict):
        if event.is_same_subcommand:
            return (
                "Subcommand already selected",
                [
                    f"The subcommand '{event.attempted}' was already implicitly "
                    f"selected when you used the flag '{event.trigger_flag}'.",
                    "",
                    f"Try removing '{event.attempted}' from your command.",
                ],
            )
        return (
            "Conflicting subcommand selection",
            [
                f"Cannot select subcommand '{event.attempted}' because "
                f"'{event.already_selected}'",
                f"was already implicitly selected when you used the flag "
                f"'{event.trigger_flag}'.",
                "",
                f"The flag '{event.trigger_flag}' belongs to the default subcommand",
                f"'{event.already_selected}', which implicitly selected it.",
                "",
                "Either:",
                f"  • Remove the conflicting '{event.trigger_flag}' flag, or",
                f"  • Move '{event.attempted}' earlier in the command",
            ],
        )

    if isinstance(event, BadValue):
        arg = event.argument
        if event.reason == "fixed":
            flag_name = "/".join(arg.lowered.name_or_flags)
            default_repr = (
                repr(arg.field.default)
                if not _singleton.is_missing(arg.field.default)
                else "(no default)"
            )
            return (
                "Fixed argument cannot accept a value",
                [
                    fmt.text(
                        "Argument ",
                        fmt.text["bold"](flag_name),
                        f" is fixed to {default_repr} and cannot",
                        f" accept the value {event.offending_value!r}.",
                    )
                ],
            )
        # reason == "too_few_values": two historical phrasings, by arity.
        if isinstance(arg.lowered.nargs, int):
            return (
                "Missing argument",
                [
                    f"Missing value for argument '{arg.display_name()}'. "
                    f"Expected {arg.lowered.nargs} values."
                ],
            )
        # Variadic "+" case had no title (the message was the title).
        return (
            f"Missing value for argument '{arg.display_name()}'. "
            f"Expected at least one value.",
            [],
        )

    if isinstance(event, InvalidChoice):
        arg = event.argument
        return (
            "Invalid choice",
            [
                fmt.text(
                    "invalid choice ",
                    fmt.text["bright_red", "bold"](f"'{event.value}'"),
                    " for argument ",
                    fmt.text["bold"](f"'{arg.display_name()}'"),
                    ". Expected one of ",
                    fmt.text["cyan"](str(arg.lowered.choices)),
                    ".",
                )
            ],
        )

    if isinstance(event, MissingMutexGroup):
        plural = len(event.groups) > 1
        group_lines: list[Any] = []
        for group in event.groups:
            arg_strs = []
            for arg_ctx in group:
                arg = arg_ctx.arg
                if arg.is_positional():
                    arg_strs.append(f"'{arg.lowered.name_or_flags[-1]}'")
                else:
                    arg_strs.append(f"{', '.join(arg.lowered.name_or_flags)}")
            group_lines.append(f"  • {', '.join(arg_strs)}")
        return (
            "Required mutex groups" if plural else "Required mutex group",
            [
                "Missing required argument groups:"
                if plural
                else "Missing required argument group:",
                *group_lines,
            ],
        )

    if isinstance(event, MissingSubcommand):
        subcommand_names = list(event.subcommand_spec.parser_from_name.keys())
        choices_str = " {" + ", ".join(subcommand_names) + "}"
        if event.found_token is not None:
            message = fmt.text(
                "Expected one of",
                fmt.text["cyan"](choices_str),
                ", but found: ",
                fmt.text["bright_red", "bold"](f"'{event.found_token}'"),
                ".",
            )
        else:
            message = fmt.text(
                "Expected one of",
                fmt.text["cyan"](choices_str),
                ".",
            )
        return ("Missing subcommand", [message])

    if isinstance(event, MissingArgs):
        from ._arguments import generate_argument_helptext

        content: list[Any] = []
        for argprog, arglist in event._args_from_prog().items():
            content.append(fmt.text("Missing from ", fmt.text["green"](argprog), ":"))
            for arg in arglist:
                content.append(
                    fmt.cols(("", 4), fmt.text["bold"](arg.get_invocation_text()[1]))
                )
                helptext = generate_argument_helptext(arg, arg.lowered)
                if len(helptext) > 0:
                    content.append(fmt.cols(("", 8), helptext))

        if len(event.unrecognized_tokens) > 0:
            content.append(fmt.hr["red"]())
            content.append("Unrecognized options:")
            content.append(fmt.cols(("", 4), fmt.rows(*event.unrecognized_tokens)))

        return ("Required options", content)

    raise KeyError(type(event).__name__)


def _fire_and_exit(
    event: ParseErrorEvent,
    *,
    console_outputs: bool,
    add_help: bool,
) -> NoReturn:
    """Fire the parse-error hook for ``event`` (letting a hook raise to take
    over), then render and print ``event``'s standard error and exit.

    Valid for every event that has a rendering in :func:`_render` -- i.e. all
    but ``UnrecognizedArgs`` and ``InstantiationFailure``, which fire the hook
    directly (gated on :func:`_has_hook`) and use their dedicated renderers. The
    hook is invoked unconditionally here, so callers do not gate on
    :func:`_has_hook`.
    """
    from ._backends import _tyro_help_formatting

    _fire(event)
    title, contents = _render(event)
    _tyro_help_formatting.error_and_exit(
        title,
        *contents,
        prog=event._help_progs(),
        console_outputs=console_outputs,
        add_help=add_help,
    )


def fire_and_exit_instantiation_failure(
    event: InstantiationFailure,
    *,
    arg_fallback: Any,
    add_help: bool,
) -> NoReturn:
    """Fire the parse-error hook for an :class:`InstantiationFailure`, then draw
    its bespoke "Value error" box and exit.

    Unlike :func:`_fire_and_exit`, this event is not handled by :func:`_render`:
    it draws a box with a non-bold "Value error" title and a "For full helptext,
    see ..." footer that differs from the standard ``error_and_exit`` box. The
    hook is fired here (gated on :func:`_has_hook`, since building the event is
    cheap but firing should still be skipped when nothing is registered).

    Args:
        event: The constructed failure event.
        arg_fallback: The original ``InstantiationError.arg``. When
            ``event.argument`` is set, it is used for rendering; otherwise this
            value is stringified into the error title (it carries context that
            does not fit an :class:`ArgumentDefinition`).
        add_help: Whether to append the help footer.
    """
    import sys

    from . import _arguments
    from . import _fmtlib as fmt

    if _has_hook():
        _fire(event)

    # Emulate argparse's error behavior when invalid arguments are passed in.
    error_box_rows: list[str | fmt.Element] = []
    if event.argument is not None:
        arg = event.argument
        display_name = (
            str(arg.lowered.metavar)
            if arg.is_positional()
            else "/".join(arg.lowered.name_or_flags)
        )
        error_box_rows.extend(
            [
                fmt.text(
                    fmt.text["bright_red", "bold"](f"Error parsing {display_name}:"),
                    " ",
                    event.message,
                ),
                fmt.hr["red"](),
                "Argument helptext:",
                fmt.cols(
                    ("", 4),
                    fmt.rows(
                        arg.get_invocation_text()[1],
                        _arguments.generate_argument_helptext(arg, arg.lowered),
                    ),
                ),
            ]
        )
    else:
        error_box_rows.append(
            fmt.text(
                fmt.text["bright_red", "bold"](f"Error parsing {arg_fallback}:"),
                " ",
                event.message,
            )
        )

    if add_help:
        error_box_rows.extend(
            [
                fmt.hr["red"](),
                fmt.text(
                    "For full helptext, see ",
                    fmt.text["bold"](f"{event.prog} --help"),
                ),
            ]
        )
    print(
        fmt.box["red"](fmt.text["red"]("Value error"), fmt.rows(*error_box_rows)),
        file=sys.stderr,
        flush=True,
    )
    sys.exit(2)
