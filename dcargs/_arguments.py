import argparse
import dataclasses
import enum
from typing import Any, Dict, Optional, Set, Tuple, Type, TypeVar, Union

from . import _docstrings, _instantiators


@dataclasses.dataclass(frozen=True)
class ArgumentDefinition:
    """Options for defining arguments. Contains all necessary arguments for argparse's
    add_argument() method.

    TODO: this class (as well as major other parts of this library) has succumbed a bit
    to entropy and could benefit from some refactoring."""

    prefix: str  # Prefix for nesting.
    field: dataclasses.Field  # Corresponding dataclass field.
    parent_class: Type  # Class that this field belongs to.

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
    required: Optional[bool] = None
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

        kwargs.pop("field")
        kwargs.pop("parent_class")
        kwargs.pop("prefix")
        kwargs.pop("instantiator")
        kwargs.pop("name")

        # Note that the name must be passed in as a position argument.
        parser.add_argument(self.get_flag(), **kwargs)

    def get_flag(self) -> str:
        """Get --flag representation, with a prefix applied for nested dataclasses."""
        return "--" + (self.prefix + self.name).replace("_", "-")

    @staticmethod
    def make_from_field(
        parent_class: Type,
        field: dataclasses.Field,
        type_from_typevar: Dict[TypeVar, Type],
        default: Optional[Any],
    ) -> "ArgumentDefinition":
        """Create an argument definition from a field. Also returns a field action, which
        specifies special instructions for reconstruction."""

        assert field.init, "Field must be in class constructor"

        arg = ArgumentDefinition(
            prefix="",
            field=field,
            parent_class=parent_class,
            instantiator=None,
            name=field.name,
            type=field.type,
            default=default,
        )
        arg = _transform_required_if_default_set(arg)
        arg = _transform_handle_boolean_flags(arg)
        arg = _transform_recursive_instantiator_from_type(arg, type_from_typevar)
        arg = _transform_generate_helptext(arg)
        arg = _transform_convert_defaults_to_strings(arg)
        return arg


def _transform_required_if_default_set(arg: ArgumentDefinition) -> ArgumentDefinition:
    """Set `required=True` if a default value is set."""

    # Don't set if default is set, or if required flag is already set.
    if arg.default is not None:
        return dataclasses.replace(arg, required=False)
    else:
        return dataclasses.replace(arg, required=True)


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
    docstring_help = _docstrings.get_field_docstring(arg.parent_class, arg.field.name)
    if docstring_help is not None:
        # Note that the percent symbol needs some extra handling in argparse.
        # https://stackoverflow.com/questions/21168120/python-argparse-errors-with-in-help-string
        docstring_help = docstring_help.replace("%", "%%")
        help_parts.append(docstring_help)

    if arg.action is not None:
        # Don't show defaults for boolean flags.
        assert arg.action in ("store_true", "store_false")
    elif arg.default is not None and isinstance(arg.default, enum.Enum):
        # Special case for enums.
        help_parts.append(f"(default: {arg.default.name})")
    elif not arg.required:
        # General case. We intentionally don't use the % template, because the default
        # will be casted to a string and that can make unnecessary quotation marks
        # appear in the helptext.
        help_parts.append(f"(default: {arg.default})")

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
    elif arg.nargs is not None:
        return dataclasses.replace(arg, default=tuple(map(as_str, arg.default)))
    else:
        return dataclasses.replace(arg, default=as_str(arg.default))
