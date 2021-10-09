import collections.abc
import dataclasses
import enum
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Set, Type, Union

from typing_extensions import Final, Literal, _AnnotatedAlias  # Backward compat

from . import _docstrings, _strings

if TYPE_CHECKING:
    from ._parsers import Parser


class FieldRole(enum.Enum):
    VANILLA_FIELD = enum.auto()
    TUPLE = enum.auto()
    ENUM = enum.auto()
    NESTED_DATACLASS = enum.auto()  # Singular nested dataclass
    SUBPARSERS = enum.auto()  # Unions over dataclasses


@dataclasses.dataclass(frozen=True)
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
    dest: Optional[str] = None

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

        assert field.init, "Field must be in class constructor"

        # Create initial argument
        arg = ArgumentDefinition(
            name=field.name,
            field=field,
            parent_class=parent_class,
            # Default role -- this can be overridden by transforms to enable various
            # special behaviours. (such as for enums)
            role=FieldRole.VANILLA_FIELD,
            type=field.type,
        )

        # Propagate argument through transforms until stable
        prev_arg = arg
        while True:
            for transform in _argument_transforms:
                arg = transform(arg)
            if arg == prev_arg:
                break
            prev_arg = arg
        return arg


# Argument transformations


def _unwrap_no_ops(arg: ArgumentDefinition) -> ArgumentDefinition:
    """Treat Final[T] as just T."""
    if hasattr(arg.type, "__origin__") and arg.type.__origin__ is Final:  # type: ignore
        (typ,) = arg.type.__args__  # type: ignore
        return dataclasses.replace(
            arg,
            type=typ,
        )
    else:
        return arg


def _unwrap_annotated(arg: ArgumentDefinition) -> ArgumentDefinition:
    """Treat Annotated[T, annotation] as just T."""
    if hasattr(arg.type, "__class__") and arg.type.__class__ == _AnnotatedAlias:
        typ = arg.type.__origin__  # type: ignore
        return dataclasses.replace(
            arg,
            type=typ,
        )
    else:
        return arg


def _handle_optionals(arg: ArgumentDefinition) -> ArgumentDefinition:
    """Transform for handling Optional[T] types. Sets default to None and marks arg as
    not required."""
    if hasattr(arg.type, "__origin__") and arg.type.__origin__ is Union:  # type: ignore
        options = set(arg.type.__args__)  # type: ignore
        assert (
            len(options) == 2 and type(None) in options
        ), "Union must be either over dataclasses (for subparsers) or Optional"
        (typ,) = options - {type(None)}
        required = False
        return dataclasses.replace(
            arg,
            type=typ,
            required=required,
        )
    else:
        return arg


def _populate_defaults(arg: ArgumentDefinition) -> ArgumentDefinition:
    """Populate default values."""
    if arg.default is not None:
        # Skip if another handler has already populated the default
        return arg

    default = None
    required = True
    if arg.field.default is not dataclasses.MISSING:
        default = arg.field.default
        required = False
    elif arg.field.default_factory is not dataclasses.MISSING:  # type: ignore
        default = arg.field.default_factory()  # type: ignore
        required = False

    if arg.required is not None:
        required = arg.required

    return dataclasses.replace(arg, default=default, required=required)


def _bool_flags(arg: ArgumentDefinition) -> ArgumentDefinition:
    """For booleans, we use a `store_true` action."""
    if arg.type != bool:
        return arg

    if arg.default is None:
        return dataclasses.replace(
            arg,
            type=_strings.bool_from_string,  # type: ignore
            metavar="{True,False}",
        )
    elif arg.default is False:
        return dataclasses.replace(
            arg,
            action="store_true",
            type=None,
        )
    elif arg.default is True:
        return dataclasses.replace(
            arg,
            dest=arg.name,
            name="no_" + arg.name,
            action="store_false",
            type=None,
        )
    else:
        assert False, "Invalid default"


def _nargs_from_sequences_and_lists(arg: ArgumentDefinition) -> ArgumentDefinition:
    """Transform for handling Sequence[T] and list types."""
    if hasattr(arg.type, "__origin__") and arg.type.__origin__ in (  # type: ignore
        collections.abc.Sequence,  # different from typing.Sequence!
        list,  # different from typing.List!
    ):
        assert len(arg.type.__args__) == 1  # type: ignore
        (typ,) = arg.type.__args__  # type: ignore

        return dataclasses.replace(
            arg,
            type=typ,
            # `*` is >=0 values, `+` is >=1 values
            # We're going to require at least 1 value; if a user wants to accept no
            # input, they can use Optional[Tuple[...]]
            nargs="+",
        )
    else:
        return arg


def _nargs_from_tuples(arg: ArgumentDefinition) -> ArgumentDefinition:
    """Transform for handling Tuple[T, T, ...] types."""
    if hasattr(arg.type, "__origin__") and arg.type.__origin__ == tuple:  # type: ignore
        argset = set(arg.type.__args__)  # type: ignore
        argset_no_ellipsis = argset - {Ellipsis}  #
        assert len(argset_no_ellipsis) == 1, "Tuples must be of a single type!"

        if argset != argset_no_ellipsis:
            # `*` is >=0 values, `+` is >=1 values
            # We're going to require at least 1 value; if a user wants to accept no
            # input, they can use Optional[Tuple[...]]
            nargs = "+"
        else:
            nargs = len(arg.type.__args__)  # type: ignore
        (typ,) = argset_no_ellipsis

        assert arg.role is FieldRole.VANILLA_FIELD
        return dataclasses.replace(
            arg,
            nargs=nargs,
            type=typ,
            role=FieldRole.TUPLE,
        )
    else:
        return arg


def _choices_from_literals(arg: ArgumentDefinition) -> ArgumentDefinition:
    """For literal types, set choices."""
    if hasattr(arg.type, "__origin__") and arg.type.__origin__ is Literal:  # type: ignore
        choices = set(arg.type.__args__)  # type: ignore
        assert (
            len(set(map(type, choices))) == 1
        ), "All choices in literal must have the same type!"
        return dataclasses.replace(
            arg,
            type=type(arg.type.__args__[0]),  # type: ignore
            choices=choices,
        )
    else:
        return arg


def _enums_as_strings(arg: ArgumentDefinition) -> ArgumentDefinition:
    """For enums, use string representations."""
    if isinstance(arg.type, type) and issubclass(arg.type, enum.Enum):
        if arg.choices is None:
            choices = set(x.name for x in arg.type)
        else:
            choices = set(x.name for x in arg.choices)

        assert arg.role is FieldRole.VANILLA_FIELD
        return dataclasses.replace(
            arg,
            choices=choices,
            type=str,
            default=None if arg.default is None else arg.default.name,
            role=FieldRole.ENUM,
        )
    else:
        return arg


def _generate_helptext(arg: ArgumentDefinition) -> ArgumentDefinition:
    """Generate helptext from docstring and argument name."""
    if arg.help is None:
        help_parts = []
        docstring_help = _docstrings.get_field_docstring(
            arg.parent_class, arg.field.name
        )
        if docstring_help is not None:
            help_parts.append(docstring_help)

        if arg.default is not None and hasattr(arg.default, "name"):
            # Special case for enums
            help_parts.append(f"(default: {arg.default.name})")
        elif arg.default is not None:
            # General case
            help_parts.append("(default: %(default)s)")

        return dataclasses.replace(arg, help=" ".join(help_parts))
    else:
        return arg


def _use_type_as_metavar(arg: ArgumentDefinition) -> ArgumentDefinition:
    """Communicate the argument type using the metavar."""
    if hasattr(arg.type, "__name__") and arg.choices is None and arg.metavar is None:
        return dataclasses.replace(
            arg, metavar=arg.type.__name__.upper()  # type: ignore
        )
    else:
        return arg


_argument_transforms: List[Callable[[ArgumentDefinition], ArgumentDefinition]] = [
    _unwrap_no_ops,
    _unwrap_annotated,
    _handle_optionals,
    _populate_defaults,
    _bool_flags,
    _nargs_from_sequences_and_lists,
    _nargs_from_tuples,
    _choices_from_literals,
    _enums_as_strings,
    _generate_helptext,
    _use_type_as_metavar,
]
