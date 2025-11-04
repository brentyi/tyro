"""Rules for taking high-level field definitions and lowering them into inputs for
argparse's `add_argument()`."""

from __future__ import annotations

import collections.abc
import dataclasses
import json
import shlex
from functools import cached_property
from typing import (
    Any,
    Callable,
    Iterable,
    Literal,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from typing_extensions import get_origin

from . import _fields, _settings, _singleton, _strings
from . import _fmtlib as fmt
from ._backends import _argparse as argparse
from .conf import _markers
from .constructors import (
    ConstructorRegistry,
    PrimitiveTypeInfo,
    UnsupportedTypeAnnotationError,
)

_T = TypeVar("_T")


def flag_to_inverse(option_string: str) -> str:
    """Converts --flag to --no-flag, --child.flag to --child.no-flag, etc."""
    if "." not in option_string:
        option_string = "--no" + _strings.get_delimeter() + option_string[2:]
    else:
        # Loose heuristic for where to add the no-/no_ prefix.
        left, _, right = option_string.rpartition(".")
        option_string = left + ".no" + _strings.get_delimeter() + right
    return option_string


class BooleanOptionalAction(argparse.Action):
    """Adapted from https://github.com/python/cpython/pull/27672"""

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        default: _T | str | None = None,
        type: Callable[[str], _T] | argparse.FileType | None = None,
        choices: Iterable[_T] | None = None,
        required: bool = False,
        help: str | None = None,
        metavar: str | tuple[str, ...] | None = None,
    ) -> None:
        _option_strings = []
        self._no_strings = set()
        for option_string in option_strings:
            _option_strings.append(option_string)

            if option_string.startswith("--"):
                option_string = flag_to_inverse(option_string)
                self._no_strings.add(option_string)
                _option_strings.append(option_string)

        super().__init__(
            option_strings=_option_strings,
            dest=dest,
            nargs=0,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        if option_string in self.option_strings:
            assert option_string is not None
            setattr(namespace, self.dest, option_string not in self._no_strings)


@dataclasses.dataclass(frozen=True)
class ArgumentDefinition:
    """Structure containing everything needed to define an argument."""

    intern_prefix: str  # True prefix. (eg for the argument's dest field)
    extern_prefix: str  # User-facing prefix.
    subcommand_prefix: str  # Prefix for nesting.
    field: _fields.FieldDefinition

    def __post_init__(self) -> None:
        if (
            _markers.Fixed in self.field.markers
            or _markers.Suppress in self.field.markers
        ) and self.field.default in _singleton.MISSING_AND_MISSING_NONPROP:
            raise UnsupportedTypeAnnotationError(
                f"Field {self.field.intern_name} is missing a default value!"
            )

    def get_output_key(self) -> str:
        """Get key used for this arg in the parsed output dict."""
        if self.is_positional():
            return self.lowered.name_or_flags[-1]
        else:
            assert self.lowered.dest is not None
            return self.lowered.dest

    def is_positional(self) -> bool:
        """Returns True if the argument should be positional in the commandline."""
        return (
            # Explicit positionals.
            _markers.Positional in self.field.markers
            or (
                # Make required arguments positional.
                _markers.PositionalRequiredArgs in self.field.markers
                and self.field.default in _singleton.MISSING_AND_MISSING_NONPROP
            )
            # Argumens with no names (like in DummyWrapper) should be
            # positional.
            or (
                self.field.extern_name == ""
                and self.field.intern_name == "__tyro_dummy_inner__"
            )
        )

    def add_argument(
        self, parser: Union[argparse.ArgumentParser, argparse._ArgumentGroup]
    ) -> None:
        """Add a defined argument to a parser."""

        # Get keyword arguments, with None values removed.
        kwargs = dict(self.lowered.__dict__)  # type: ignore
        kwargs.pop("instance_from_str")
        kwargs.pop("str_from_instance")
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        name_or_flags = kwargs.pop("name_or_flags")

        if self.is_positional():
            if "required" in kwargs:
                kwargs.pop("required")  # Can't be passed in for positional arguments.
            if len(name_or_flags) > 1:
                import warnings

                warnings.warn(
                    f"Aliases were specified, but {name_or_flags} is positional. Aliases will be ignored."
                )
                name_or_flags = name_or_flags[-1:]

        if kwargs.get("action", None) == "boolean_optional_action":
            kwargs["action"] = BooleanOptionalAction

        # Add argument, with aliases if available.
        arg = parser.add_argument(*name_or_flags, **kwargs)

        # Do our best to tab complete paths.
        # There will be false positives here, but if choices is unset they should be
        # harmless.
        # Note: shtab is now optional, so we only set completion hints if available.
        if "choices" not in kwargs:
            name_suggests_dir = (
                # The conditions are intended to be conservative; if a directory path is
                # registered as a normal file one that's OK, the reverse on the other
                # hand will be overly restrictive.
                self.field.intern_name.endswith("_dir")
                or self.field.intern_name.endswith("_directory")
                or self.field.intern_name.endswith("_folder")
            )
            name_suggests_path = (
                self.field.intern_name.endswith("_file")
                or self.field.intern_name.endswith("_path")
                or self.field.intern_name.endswith("_filename")
                or name_suggests_dir
            )
            complete_as_path = (
                # Catch types like Path, List[Path], Tuple[Path, ...] etc.
                "Path" in str(self.field.type_stripped)
                # For string types, we require more evidence.
                or ("str" in str(self.field.type_stripped) and name_suggests_path)
            )
            if complete_as_path:
                try:
                    import shtab

                    arg.complete = shtab.DIRECTORY if name_suggests_dir else shtab.FILE  # type: ignore
                except ImportError:
                    # shtab is optional; if not available, skip completion hints.
                    pass

    @cached_property
    def lowered(self) -> LoweredArgumentDefinition:
        """Lowered argument definition, generated by applying a sequence of rules."""
        # Each rule will mutate the lowered object. This is (unfortunately)
        # much faster than a functional approach.
        lowered = LoweredArgumentDefinition()
        _rule_handle_boolean_flags(self, lowered)
        _rule_apply_primitive_specs(self, lowered)
        _rule_counters(self, lowered)
        _rule_generate_helptext(self, lowered)
        _rule_set_name_or_flag_and_dest(self, lowered)
        _rule_positional_special_handling(self, lowered)
        _rule_apply_argconf(self, lowered)
        return lowered

    def is_suppressed(self) -> bool:
        """Returns if the argument is suppressed. Suppressed arguments won't be
        added to the parser."""
        return _markers.Suppress in self.field.markers or (
            _markers.SuppressFixed in self.field.markers and self.lowered.is_fixed()
        )

    def get_invocation_text(self) -> tuple[fmt._Text, fmt._Text]:
        """Returns (invocation short, invocation long)."""

        if self.is_positional():
            assert self.lowered.metavar is not None
            invocation_short = fmt.text["bold"](self.lowered.metavar)
            invocation_long = fmt.text(self.lowered.metavar)
            return invocation_short, invocation_long

        name_or_flags: list[str] = list(self.lowered.name_or_flags)
        if self.lowered.action == "boolean_optional_action":
            name_or_flags = []
            for name_or_flag in self.lowered.name_or_flags:
                name_or_flags.append(name_or_flag)
                name_or_flags.append(flag_to_inverse(name_or_flag))
            invocation_short = fmt.text(
                self.lowered.name_or_flags[0],
                " | ",
                flag_to_inverse(self.lowered.name_or_flags[0]),
            )
        elif self.lowered.metavar is not None:
            invocation_short = fmt.text(
                self.lowered.name_or_flags[0],
                " ",
                fmt.text["bold"](self.lowered.metavar),
            )
        else:
            invocation_short = fmt.text(self.lowered.name_or_flags[0])

        if self.lowered.required is not True:
            invocation_short = fmt.text("[", invocation_short, "]")

        invocation_long_parts: list[str | fmt._Text] = []
        for i, name in enumerate(name_or_flags):
            if i > 0:
                invocation_long_parts.append(", ")

            invocation_long_parts.append(name)
            if self.lowered.metavar is not None and self.lowered.metavar != "":
                invocation_long_parts.append(" ")
                invocation_long_parts.append(fmt.text["bold"](self.lowered.metavar))

        return invocation_short, fmt.text(*invocation_long_parts)


@dataclasses.dataclass
class LoweredArgumentDefinition:
    """Contains fields meant to be passed directly into argparse."""

    # Action that is called on parsed arguments. This handles conversions from strings
    # to our desired types.
    #
    # The main reason we use this instead of the standard 'type' argument is to enable
    # mixed-type tuples.
    instance_from_str: Optional[Callable] = None
    str_from_instance: Optional[Callable] = None

    def is_fixed(self) -> bool:
        """If the instantiator is set to `None`, even after all argument
        transformations, it means that we don't have a valid instantiator for an
        argument. We then mark the argument as 'fixed', with a value always equal to the
        field default."""
        return self.instance_from_str is None

    # From here on out, all fields correspond 1:1 to inputs to argparse's
    # add_argument() method.
    name_or_flags: Tuple[str, ...] = ()
    default: Optional[Any] = None
    dest: Optional[str] = None
    required: Optional[bool] = None
    action: Optional[
        Literal[
            "count", "append", "store_true", "store_false", "boolean_optional_action"
        ]
    ] = None
    nargs: Optional[Union[int, Literal["*", "?"]]] = None
    choices: Optional[Tuple[str, ...]] = None
    # Note: unlike in vanilla argparse, our metavar is always a string. We handle
    # sequences, multiple arguments, etc, manually.
    metavar: Optional[str] = None
    help: Optional[str] = None


def _rule_handle_boolean_flags(
    arg: ArgumentDefinition,
    lowered: LoweredArgumentDefinition,
) -> None:
    if arg.field.type_stripped is not bool:
        return

    if (
        arg.field.default in _singleton.MISSING_AND_MISSING_NONPROP
        or arg.is_positional()
        or _markers.FlagConversionOff in arg.field.markers
        or _markers.Fixed in arg.field.markers
    ):
        # Treat bools as a normal parameter.
        return

    # Default `False` => --flag passed in flips to `True`.
    if _markers.FlagCreatePairsOff in arg.field.markers:
        # If default is True, --flag will flip to `False`.
        # If default is False, --no-flag will flip to `True`.
        lowered.action = "store_false" if arg.field.default else "store_true"
    else:
        # Create both --flag and --no-flag.
        lowered.action = "boolean_optional_action"
    lowered.instance_from_str = lambda x: x  # argparse will directly give us a bool!
    lowered.default = arg.field.default
    return


def _rule_apply_primitive_specs(
    arg: ArgumentDefinition,
    lowered: LoweredArgumentDefinition,
) -> None:
    """The bulkiest bit: recursively analyze the type annotation and use it to determine
    how to instantiate it given some string from the commandline.

    Important: as far as argparse is concerned, all inputs are strings.

    Conversions from strings to our desired types happen in the instantiator; this is a
    bit more flexible, and lets us handle more complex types like enums and multi-type
    tuples."""

    if _markers.Fixed in arg.field.markers:
        lowered.instance_from_str = None
        lowered.metavar = "{fixed}"
        lowered.required = False
        lowered.default = _singleton.MISSING
        return
    if lowered.instance_from_str is not None:
        lowered.required = False
        return

    spec = ConstructorRegistry.get_primitive_spec(
        PrimitiveTypeInfo.make(
            cast(type, arg.field.type),
            arg.field.markers,
        )
    )
    if isinstance(spec, UnsupportedTypeAnnotationError):
        error = spec
        if arg.field.default in _singleton.MISSING_AND_MISSING_NONPROP:
            field_name = _strings.make_field_name(
                [arg.extern_prefix, arg.field.extern_name]
            )
            if field_name != "":
                raise UnsupportedTypeAnnotationError(
                    f"Unsupported type annotation for field with name `{field_name}`, which is resolved to `{arg.field.type}`. "
                    f"{error.args[0]} "
                    "To suppress this error, assign the field either a default value or a different type."
                )
            else:
                # If the field name is empty, it means we're raising an error
                # for the direct input to `tyro.cli()`. We don't need to write
                # out which specific field we're complaining about.
                raise error
        else:
            # For fields with a default, we'll get by even if there's no instantiator
            # available.
            lowered.metavar = "{fixed}"
            lowered.required = False
            lowered.default = _singleton.MISSING
            return

    # Mark lowered as required if a default is missing.
    if (
        arg.field.default in _singleton.MISSING_AND_MISSING_NONPROP
        and _markers._OPTIONAL_GROUP not in arg.field.markers
    ):
        lowered.required = True

    # We're actually going to skip the default field: if an argument is unset, the
    # MISSING value will be detected in _calling.py and the field default will
    # directly be used. This helps reduce the likelihood of issues with converting
    # the field default to a string format, then back to the desired type.
    if spec._action == "append":
        lowered.default = []
    else:
        lowered.default = _singleton.MISSING_NONPROP

    if spec._action == "append":

        def append_instantiator(x: list[list[str]]) -> Any:
            """Handle UseAppendAction effects."""
            # We'll assume that the type is annotated as Dict[...], Tuple[...], List[...], etc.
            container_type = get_origin(arg.field.type_stripped)
            if container_type is None:
                # Raw annotation, like `UseAppendAction[list]`. It's unlikely
                # that a user would use this but we can handle it.
                container_type = arg.field.type_stripped

            # Instantiate initial output.
            out = (
                arg.field.default
                if arg.field.default not in _singleton.MISSING_AND_MISSING_NONPROP
                else None
            )
            if out is None:
                out = {} if container_type is dict else []
            elif isinstance(out, dict):
                out = out.copy()
            else:
                # All sequence types will be lists for now to make sure we can
                # append to them.
                out = list(out)

            # Get + merge parts.
            parts = [spec.instance_from_str(arg_list) for arg_list in x]
            for part in parts:
                if isinstance(out, dict):
                    out.update(part)
                else:
                    out.append(part)

            # Return output with correct type.
            if container_type in (dict, Sequence, collections.abc.Sequence):
                return out
            else:
                return container_type(out)

        lowered.instance_from_str = append_instantiator
        lowered.str_from_instance = spec.str_from_instance
        lowered.choices = spec.choices
        lowered.nargs = spec.nargs if not isinstance(spec.nargs, tuple) else "*"
        lowered.metavar = spec.metavar
        lowered.action = spec._action
        lowered.required = False
        return
    else:
        lowered.instance_from_str = spec.instance_from_str
        lowered.str_from_instance = spec.str_from_instance
        lowered.choices = spec.choices
        lowered.nargs = spec.nargs if not isinstance(spec.nargs, tuple) else "*"
        lowered.metavar = spec.metavar
        lowered.action = spec._action
        return


def _rule_counters(
    arg: ArgumentDefinition,
    lowered: LoweredArgumentDefinition,
) -> None:
    """Handle counters, like -vvv for level-3 verbosity."""
    if (
        _markers.UseCounterAction in arg.field.markers
        and arg.field.type_stripped is int
        and not arg.is_positional()
    ):
        lowered.metavar = None
        lowered.nargs = None
        lowered.action = "count"
        lowered.default = 0
        lowered.required = False
        lowered.instance_from_str = (
            lambda x: x
        )  # argparse will directly give us an int!
        return


def _rule_generate_helptext(
    arg: ArgumentDefinition,
    lowered: LoweredArgumentDefinition,
) -> None:
    """Generate helptext from docstring, argument name, default values."""

    # The percent symbol needs some extra handling in argparse.
    # https://stackoverflow.com/questions/21168120/python-argparse-errors-with-in-help-string
    lowered.help = (
        generate_argument_helptext(arg, lowered).as_str_no_ansi().replace("%", "%%")
    )


def _rule_set_name_or_flag_and_dest(
    arg: ArgumentDefinition,
    lowered: LoweredArgumentDefinition,
) -> None:
    extern_name = arg.field.extern_name
    if lowered.action == "store_false":
        extern_name = "no_" + extern_name

    if (
        arg.field.argconf.prefix_name is False
        or _markers.OmitArgPrefixes in arg.field.markers
    ):
        # Strip prefixes when the argument is suppressed.
        # Still need to call make_field_name() because it converts underscores
        # to hyphens, etc.
        name_or_flag = _strings.make_field_name([extern_name])
    elif (
        _markers.OmitSubcommandPrefixes in arg.field.markers
        and arg.subcommand_prefix != ""
    ):
        # Strip subcommand prefixes, but keep following
        # prefixes.`extern_prefix` can start with the prefix corresponding to
        # the parent subcommand, but end with other prefixes correspondeding to
        # nested structures within the subcommand.
        name_or_flag = _strings.make_field_name([arg.extern_prefix, extern_name])
        strip_prefix = arg.subcommand_prefix + "."
        assert name_or_flag.startswith(strip_prefix), name_or_flag
        name_or_flag = name_or_flag[len(strip_prefix) :]
    else:
        # Standard prefixed name.
        name_or_flag = _strings.make_field_name([arg.extern_prefix, extern_name])

    # Prefix keyword arguments with --.
    if not arg.is_positional():
        name_or_flag = "--" + name_or_flag

    lowered.name_or_flags = (name_or_flag,)
    lowered.dest = _strings.make_field_name([arg.intern_prefix, arg.field.intern_name])


def _rule_positional_special_handling(
    arg: ArgumentDefinition,
    lowered: LoweredArgumentDefinition,
) -> None:
    if not arg.is_positional():
        return None

    metavar = lowered.metavar
    if lowered.required:
        nargs = lowered.nargs
    else:
        if metavar is not None:
            metavar = "[" + metavar + "]"
        if lowered.nargs == 1:
            # Optional positional arguments. This needs to be special-cased in
            # _calling.py.
            nargs = "?"
        else:
            # If lowered.nargs is either + or an int.
            nargs = "*"

    lowered.name_or_flags = (
        _strings.make_field_name([arg.intern_prefix, arg.field.intern_name]),
    )
    lowered.dest = None
    lowered.metavar = metavar
    lowered.nargs = nargs
    return


def _rule_apply_argconf(
    arg: ArgumentDefinition,
    lowered: LoweredArgumentDefinition,
) -> None:
    if arg.field.argconf.metavar is not None:
        lowered.metavar = arg.field.argconf.metavar
    if arg.field.argconf.aliases is not None:
        lowered.name_or_flags = arg.field.argconf.aliases + lowered.name_or_flags


def generate_argument_helptext(
    arg: ArgumentDefinition, lowered: LoweredArgumentDefinition
) -> fmt._Text:
    help_parts: list[str | fmt._Text] = []

    primary_help = arg.field.helptext

    if primary_help is None and _markers.Positional in arg.field.markers:
        primary_help = _strings.make_field_name(
            [arg.extern_prefix, arg.field.intern_name]
        )

    if primary_help is not None:
        help_parts.append(fmt.text["dim"](primary_help))

    if not lowered.required:
        # Get the default value.
        # Note: lowered.default is the stringified version!
        if (
            lowered.is_fixed()
            or lowered.action
            in (
                "append",
                "boolean_optional_action",
                "store_true",
                "store_false",
            )
            or arg.field.default in _singleton.MISSING_AND_MISSING_NONPROP
        ):
            # Cases where we want to use the field default directly.
            default = arg.field.default
        elif arg.field.default is _singleton.EXCLUDE_FROM_CALL:
            default = None
        else:
            # Standard cases where we convert to a string representation.
            default = (
                lowered.str_from_instance(arg.field.default)
                if lowered.str_from_instance is not None
                else None
            )

        # Get the default value label.
        if arg.field.argconf.constructor_factory is not None:
            default_label = (
                str(default)
                if arg.field.type_stripped is not json.loads
                else json.dumps(arg.field.default)
            )
        elif type(default) in (tuple, list, set):
            # For tuple types, we might have default as (0, 1, 2, 3).
            # For list types, we might have default as [0, 1, 2, 3].
            # For set types, we might have default as {0, 1, 2, 3}.
            #
            # In all cases, we want to display (default: 0 1 2 3), for consistency with
            # the format that argparse expects when we set nargs.
            assert default is not None
            default_label = " ".join(map(shlex.quote, map(str, default)))
        else:
            default_label = str(default)

        # Suffix helptext with some behavior hint, such as the default value of the argument.
        help_behavior_hint = arg.field.argconf.help_behavior_hint
        if help_behavior_hint is not None:
            behavior_hint = (
                help_behavior_hint(default_label)
                if callable(help_behavior_hint)
                else help_behavior_hint
            )
        elif lowered.instance_from_str is None:
            # Intentionally not quoted via shlex, since this can't actually be passed
            # in via the commandline.
            behavior_hint = f"(fixed to: {str(default)})"
        elif lowered.action == "count":
            # Repeatable argument.
            behavior_hint = "(repeatable)"
        elif lowered.action == "append" and (
            default in _singleton.MISSING_AND_MISSING_NONPROP
            or len(cast(tuple, default)) == 0
        ):
            behavior_hint = "(repeatable)"
        elif lowered.action == "append" and len(cast(tuple, default)) > 0:
            assert default is not None  # Just for type checker.
            behavior_hint = f"(repeatable, appends to: {default_label})"
        elif arg.field.default is _singleton.EXCLUDE_FROM_CALL:
            # ^important to use arg.field.default and not the stringified default variable.
            behavior_hint = "(unset by default)"
        elif (
            _markers._OPTIONAL_GROUP in arg.field.markers
            and default in _singleton.MISSING_AND_MISSING_NONPROP
        ):
            # Argument in an optional group, but with no default. This is typically used
            # when general (non-argument, non-dataclass) object arguments are given a
            # default, or when we use `tyro.conf.arg(constructor=...)`.
            #
            # There are some usage details that aren't communicated right now in the
            # helptext. For example: all arguments within an optional group without a
            # default should be passed in or none at all.
            behavior_hint = "(optional)"
        elif _markers._OPTIONAL_GROUP in arg.field.markers:
            # Argument in an optional group, but which also has a default.
            behavior_hint = f"(default if used: {default_label})"
        else:
            behavior_hint = f"(default: {default_label})"

        help_parts.append(
            fmt.text[
                _settings.ACCENT_COLOR if _settings.ACCENT_COLOR != "white" else "cyan"
            ](behavior_hint)
        )
    else:
        help_parts.append(fmt.text["bright_red"]("(required)"))

    return fmt.text(*help_parts, delimeter=" ")
