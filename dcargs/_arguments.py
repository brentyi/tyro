import dataclasses
import enum
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Set, Type, Union

from typing_extensions import Literal  # Python 3.7 compat

from . import _docstrings

if TYPE_CHECKING:
    from ._parsers import Parser


@dataclasses.dataclass
class ArgumentDefinition:
    """Options for defining arguments. Contains all necessary arguments for argparse's
    add_argument() method."""

    name: str
    field: dataclasses.Field
    parent_class: Type

    type: Optional[Type[Any]] = None
    help: str = ""
    required: Optional[bool] = None
    action: Optional[str] = None
    nargs: Optional[Union[int, str]] = None
    default: Optional[Any] = None
    choices: Optional[Set[Any]] = None

    def apply(self, parsers: "Parser") -> None:
        """Add a defined argument to a parser."""
        kwargs = {k: v for k, v in vars(self).items() if v is not None}
        name = "--" + kwargs.pop("name").replace("_", "-")
        kwargs.pop("field")
        kwargs.pop("parent_class")

        if "required" in kwargs and kwargs["required"]:
            parsers.required.add_argument(name, **kwargs)
        else:
            parsers.root.add_argument(name, **kwargs)

    @staticmethod
    def make_from_field(
        parent_class: Type, field: dataclasses.Field
    ) -> "ArgumentDefinition":
        """Create an argument definition from a field."""

        arg = ArgumentDefinition(
            name=field.name,
            parent_class=parent_class,
            field=field,
            type=field.type,
            help="",
        )
        for transform in _argument_transforms:
            transform(arg)
        return arg


# Argument transformations


def _bool_flags(arg: ArgumentDefinition) -> None:
    """For booleans, we use a `store_true` action."""
    if arg.type is not bool:
        return

    # TODO: what if the default value of the field is set to true by the user?
    arg.action = "store_true"
    arg.type = None
    arg.default = False
    arg.required = False


def _populate_defaults(arg: ArgumentDefinition) -> None:
    """Populate default values."""
    if arg.default is not None:
        # Skip if another handler has already populated the default
        return

    if arg.field.default is not dataclasses.MISSING:
        arg.default = arg.field.default
        arg.required = False
    elif arg.field.default_factory is not dataclasses.MISSING:  # type: ignore
        arg.default = arg.field.default_factory()  # type: ignore
        arg.required = False
    else:
        arg.required = True


def _handle_optionals(arg: ArgumentDefinition) -> None:
    """Transform for handling Optional[T] types. Sets default to None and marks arg as
    not required."""
    field = arg.field
    if hasattr(field.type, "__origin__") and field.type.__origin__ is Union:
        options = set(field.type.__args__)
        assert (
            len(options) == 2 and type(None) in options
        ), "Union must be either over dataclasses (for subparsers) or Optional"
        (arg.type,) = options - {type(None)}
        arg.required = False


def _choices_from_literals(arg: ArgumentDefinition) -> None:
    """For literal types, set choices."""
    field = arg.field

    if hasattr(field.type, "__origin__") and field.type.__origin__ is Literal:
        choices = set(field.type.__args__)
        assert (
            len(set(map(type, choices))) == 1
        ), "All choices in literal must have the same type!"
        arg.type = type(field.type.__args__[0])
        arg.choices = choices


def _enums_as_strings(arg: ArgumentDefinition) -> None:
    """For enums, use string representations."""
    if isinstance(arg.type, type) and issubclass(arg.type, enum.Enum):
        if arg.choices is None:
            arg.choices = set(x.name for x in arg.type)
        else:
            arg.choices = set(x.name for x in arg.choices)

        arg.type = str
        if arg.default is not None:
            arg.default = arg.default.name  # default should be a string type


def _use_comment_as_helptext(arg: ArgumentDefinition) -> None:
    """Read the comment corresponding to a field and use that as helptext."""
    arg.help = _docstrings.get_field_docstring(arg.parent_class, arg.name)


def _add_default_and_type_to_helptext(arg: ArgumentDefinition) -> None:
    """Populate argument helptext."""

    help_info: List[str] = []
    if hasattr(arg.type, "__name__"):
        help_info.append(f"{arg.type.__name__}")  # type: ignore

    if hasattr(arg.default, "name"):
        # Special case for enums
        help_info.append(f"default: {arg.default.name}")  # type: ignore
    elif arg.default is not None:
        # General case
        help_info.append("default: %(default)s")

    if len(arg.help) > 0:
        arg.help += " "
    arg.help += "(" + ", ".join(help_info) + ")"


_argument_transforms: List[Callable[[ArgumentDefinition], None]] = [
    _bool_flags,  # needs to come before defaults are populated
    _populate_defaults,
    _handle_optionals,
    _choices_from_literals,
    _enums_as_strings,
    _use_comment_as_helptext,
    _add_default_and_type_to_helptext,
]
