from __future__ import annotations

import argparse
import dataclasses
import enum
import shlex
from typing import Any, Dict, Optional, Set, Tuple, Type, TypeVar, Union

from . import _fields, _instantiators


@dataclasses.dataclass(frozen=True)
class ArgumentDefinition:
    """Options for defining arguments. Contains all necessary arguments for argparse's
    add_argument() method."""

    prefix: str  # Prefix for nesting.
    field: _fields.Field  # Corresponding dataclass field.

    # Action that is called on parsed arguments. This handles conversions from strings
    # to our desired types.
    instantiator: Optional[_instantiators.Instantiator]

    # Fields that will be populated initially.
    # Important: from here on out, all fields correspond 1:1 to inputs to argparse's
    # add_argument() method.
    name: str
    type: Optional[Union[Type, TypeVar]]
    default: Optional[Any]

    # Fields that will be handled by argument transformations.
    required: bool = False
    action: Optional[str] = None
    nargs: Optional[Union[int, str]] = None
    choices: Optional[Set[Any]] = None
    metavar: Optional[Union[str, Tuple[str, ...]]] = None
    help: Optional[str] = None
    dest: Optional[str] = None

    def add_argument(
        self, parser: Union[argparse.ArgumentParser, argparse._ArgumentGroup]
    ) -> None:
        """Add a defined argument to a parser."""
        kwargs = {k: v for k, v in vars(self).items() if v is not None}

        # Apply prefix for nested dataclasses.
        if "dest" in kwargs:
            kwargs["dest"] = self.prefix + kwargs["dest"]

        # Important: as far as argparse is concerned, all inputs are strings.
        #
        # Conversions from strings to our desired types happen in the "field action";
        # this is a bit more flexible, and lets us handle more complex types like enums
        # and multi-type tuples.
        if "type" in kwargs:
            kwargs["type"] = str
        if "choices" in kwargs:
            kwargs["choices"] = list(map(str, kwargs["choices"]))

        kwargs.pop("prefix")
        kwargs.pop("field")
        kwargs.pop("instantiator")
        kwargs.pop("name")

        # Note that the name must be passed in as a position argument.
        parser.add_argument(self.get_flag(), **kwargs)

    def get_flag(self) -> str:
        """Get --flag representation, with a prefix applied for nested dataclasses."""
        if self.field.positional:
            return (self.prefix + self.name).replace("_", "-")
        else:
            return "--" + (self.prefix + self.name).replace("_", "-")

    @staticmethod
    def from_field(
        field: _fields.Field,
        type_from_typevar: Dict[TypeVar, Type],
    ) -> ArgumentDefinition:
        """"""
        arg = ArgumentDefinition(
            prefix="",
            field=field,
            instantiator=None,
            name=field.name,
            type=field.typ,
            default=field.default,
        )
        arg = _transform_required_if_default_set(arg)
        arg = _transform_handle_boolean_flags(arg)
        arg = _transform_recursive_instantiator_from_type(arg, type_from_typevar)
        arg = _transform_generate_helptext(arg)
        arg = _transform_convert_defaults_to_strings(arg)
        arg = _transform_positional_special_handling(arg)
        return arg


def _transform_required_if_default_set(arg: ArgumentDefinition) -> ArgumentDefinition:
    """Set `required=True` if a default value is set."""

    # Mark arg as required if a default is set.
    if arg.default is None:
        return dataclasses.replace(arg, required=True)

    return dataclasses.replace(arg)


def _transform_handle_boolean_flags(arg: ArgumentDefinition) -> ArgumentDefinition:
    """"""
    if arg.type is not bool:
        return arg

    if arg.default is None:
        # If no default is passed in, we treat bools as a normal parameter.
        return arg
    elif arg.default is False:
        # Default `False` => --flag passed in flips to `True`.
        return dataclasses.replace(
            arg,
            action="store_true",
            type=None,
            instantiator=lambda x: x,  # argparse will directly give us a bool!
        )
    elif arg.default is True:
        # Default `True` => --no-flag passed in flips to `False`.
        return dataclasses.replace(
            arg,
            dest=arg.name,
            name="no_" + arg.name,
            action="store_false",
            type=None,
            instantiator=lambda x: x,  # argparse will directly give us a bool!
        )
    else:
        assert False, "Invalid default"


def _transform_recursive_instantiator_from_type(
    arg: ArgumentDefinition,
    type_from_typevar: Dict[TypeVar, Type],
) -> ArgumentDefinition:
    """The bulkiest bit: recursively analyze the type annotation and use it to determine how"""
    if arg.instantiator is not None:
        return arg

    instantiator, metadata = _instantiators.instantiator_from_type(
        arg.type,  # type: ignore
        type_from_typevar,
    )
    return dataclasses.replace(
        arg,
        instantiator=instantiator,
        choices=metadata.choices,
        nargs=metadata.nargs,
        required=(not metadata.is_optional) and arg.required,
        # Ignore metavar if choices is set.
        metavar=metadata.metavar if metadata.choices is None else None,
    )


def _transform_generate_helptext(arg: ArgumentDefinition) -> ArgumentDefinition:
    """Generate helptext from docstring and argument name."""
    help_parts = []

    docstring_help = arg.field.helptext

    if docstring_help is not None and docstring_help != "":
        # Note that the percent symbol needs some extra handling in argparse.
        # https://stackoverflow.com/questions/21168120/python-argparse-errors-with-in-help-string
        docstring_help = docstring_help.replace("%", "%%")
        help_parts.append(docstring_help)
    elif arg.field.positional:
        help_parts.append(str(arg.metavar))

    if arg.action is not None:
        # Don't show defaults for boolean flags.
        assert arg.action in ("store_true", "store_false")
    elif arg.default is not None and isinstance(arg.default, enum.Enum):
        # Special case for enums.
        help_parts.append(f"(default: {arg.default.name})")
    elif not arg.required:
        # Include default value in helptext. We intentionally don't use the % template
        # because the types of all arguments are set to strings, which will cause the
        # default to be casted to a string and introduce extra quotation marks.
        if arg.nargs is not None and hasattr(arg.default, "__iter__"):
            # For tuple types, we might have arg.default as (0, 1, 2, 3).
            # For list types, we might have arg.default as [0, 1, 2, 3].
            # For set types, we might have arg.default as {0, 1, 2, 3}.
            #
            # In all cases, we want to display (default: 0 1 2 3), for consistency with
            # the format that argparse expects when we set nargs.
            assert arg.default is not None  # Just for type checker.
            default_parts = map(shlex.quote, map(str, arg.default))
            help_parts.append(f"(default: {' '.join(default_parts)})")
        else:
            help_parts.append(f"(default: {shlex.quote(str(arg.default))})")

    return dataclasses.replace(arg, help=" ".join(help_parts))


def _transform_convert_defaults_to_strings(
    arg: ArgumentDefinition,
) -> ArgumentDefinition:
    """Sets all default values to strings, as required as input to our instantiator
    functions. Special-cased for enums."""

    def as_str(x: Any) -> str:
        if isinstance(x, enum.Enum):
            return x.name
        else:
            return str(x)

    if arg.default is None or arg.action is not None:
        return arg
    elif arg.nargs is not None and arg.nargs != "?":
        return dataclasses.replace(arg, default=tuple(map(as_str, arg.default)))
    else:
        return dataclasses.replace(arg, default=as_str(arg.default))


def _transform_positional_special_handling(
    arg: ArgumentDefinition,
) -> ArgumentDefinition:
    """Special handling for positional args."""

    if not arg.field.positional:
        return arg

    return dataclasses.replace(
        arg,
        metavar=(arg.prefix + arg.name).upper(),
        required=None,
        nargs="?" if not arg.required else arg.nargs,
    )
