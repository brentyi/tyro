import collections.abc
import dataclasses
import enum
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Set, Type, Union

from typing_extensions import Literal  # Python 3.7 compat

from . import _docstrings

if TYPE_CHECKING:
    from ._parsers import Parser


class FieldRole(enum.Enum):
    VANILLA_FIELD = enum.auto()
    TUPLE = enum.auto()
    ENUM = enum.auto()
    NESTED_DATACLASS = enum.auto()  # Singular nested dataclass
    SUBPARSERS = enum.auto()  # Unions over dataclasses


@dataclasses.dataclass
class ArgumentDefinition:
    """Options for defining arguments. Contains all necessary arguments for argparse's
    add_argument() method."""

    # Fields that will be populated initially
    name: str
    field: dataclasses.Field
    parent_class: Type
    role: FieldRole
    type: Optional[Type[Any]]

    # Fields that will be handled by argument transformations
    required: Optional[bool] = None
    action: Optional[str] = None
    nargs: Optional[Union[int, str]] = None
    default: Optional[Any] = None
    choices: Optional[Set[Any]] = None
    metavar: Optional[str] = None
    help: Optional[str] = None

    def apply(self, parsers: "Parser") -> None:
        """Add a defined argument to a parser."""
        kwargs = {k: v for k, v in vars(self).items() if v is not None}
        name = "--" + kwargs.pop("name").replace("_", "-")
        kwargs.pop("field")
        kwargs.pop("parent_class")
        kwargs.pop("role")

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
            field=field,
            parent_class=parent_class,
            role=FieldRole.VANILLA_FIELD,
            type=field.type,
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
    if hasattr(arg.type, "__origin__") and arg.type.__origin__ is Union:  # type: ignore
        options = set(arg.type.__args__)  # type: ignore
        assert (
            len(options) == 2 and type(None) in options
        ), "Union must be either over dataclasses (for subparsers) or Optional"
        (arg.type,) = options - {type(None)}
        arg.required = False


def _nargs_from_sequences_and_lists(arg: ArgumentDefinition) -> None:
    """Transform for handling Sequence[T] and list types."""
    if hasattr(arg.type, "__origin__") and arg.type.__origin__ in (  # type: ignore
        collections.abc.Sequence,  # different from typing.Sequence!
        list,  # different from typing.List!
    ):
        assert len(arg.type.__args__) == 1  # type: ignore
        (arg.type,) = arg.type.__args__  # type: ignore

        # `*` is >=0 values, `+` is >=1 values
        # We're going to require at least 1 value; if a user wants to accept no
        # input, they can use Optional[Tuple[...]]
        arg.nargs = "+"


def _nargs_from_tuples(arg: ArgumentDefinition) -> None:
    """Transform for handling Tuple[T, T, ...] types."""
    if hasattr(arg.type, "__origin__") and arg.type.__origin__ == tuple:  # type: ignore
        argset = set(arg.type.__args__)  # type: ignore
        argset_no_ellipsis = argset - {Ellipsis}  #
        assert len(argset_no_ellipsis) == 1, "Tuples must be of a single type!"

        if argset != argset_no_ellipsis:
            # `*` is >=0 values, `+` is >=1 values
            # We're going to require at least 1 value; if a user wants to accept no
            # input, they can use Optional[Tuple[...]]
            arg.nargs = "+"
        else:
            arg.nargs = len(arg.type.__args__)  # type: ignore
        (arg.type,) = argset_no_ellipsis

        assert arg.role is FieldRole.VANILLA_FIELD
        arg.role = FieldRole.TUPLE


def _choices_from_literals(arg: ArgumentDefinition) -> None:
    """For literal types, set choices."""
    if hasattr(arg.type, "__origin__") and arg.type.__origin__ is Literal:  # type: ignore
        choices = set(arg.type.__args__)  # type: ignore
        assert (
            len(set(map(type, choices))) == 1
        ), "All choices in literal must have the same type!"
        arg.type = type(arg.type.__args__[0])  # type: ignore
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

        assert arg.role is FieldRole.VANILLA_FIELD
        arg.role = FieldRole.ENUM


def _use_comment_as_helptext(arg: ArgumentDefinition) -> None:
    """Read the comment corresponding to a field and use that as helptext."""
    arg.help = _docstrings.get_field_docstring(arg.parent_class, arg.name)


def _add_default_and_type_to_helptext(arg: ArgumentDefinition) -> None:
    """Populate argument helptext."""

    assert arg.help is not None

    if arg.default is not None and hasattr(arg.default, "name"):
        # Special case for enums
        default_helptext = f"(default: {arg.default.name})"
    elif arg.default is not None:
        # General case
        default_helptext = "(default: %(default)s)"
    else:
        return

    if len(arg.help) > 0:
        arg.help += " "
    arg.help += default_helptext


def _use_type_as_metavar(arg: ArgumentDefinition) -> None:
    """Communicate the argument type using the metavar."""
    if hasattr(arg.type, "__name__") and arg.choices is None:
        arg.metavar = arg.type.__name__.upper()  # type: ignore


_argument_transforms: List[Callable[[ArgumentDefinition], None]] = [
    _bool_flags,  # needs to come before defaults are populated
    _populate_defaults,
    _handle_optionals,
    _nargs_from_sequences_and_lists,
    _nargs_from_tuples,
    _choices_from_literals,
    _enums_as_strings,
    _use_comment_as_helptext,
    _add_default_and_type_to_helptext,
    _use_type_as_metavar,
]
