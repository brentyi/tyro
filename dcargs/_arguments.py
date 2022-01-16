import argparse
import collections.abc
import dataclasses
import enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from typing_extensions import Final, Literal, _AnnotatedAlias, get_args, get_origin

from . import _construction, _docstrings


def _no_op_action(x):
    return x


@dataclasses.dataclass(frozen=True)
class ArgumentDefinition:
    """Options for defining arguments. Contains all necessary arguments for argparse's
    add_argument() method."""

    prefix: str  # Prefix for nesting.
    field: dataclasses.Field  # Corresponding dataclass field.
    parent_class: Type  # Class that this field belongs to.

    # Action that is called on parsed arguments. This handles conversions from strings
    # to our desired types.
    field_action: _construction.FieldAction

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

        # Important: as far as argparse is concerned, all inputs are strings.
        # Conversions from strings to our desired types happen in the "field action";
        # this is a bit more flexible, and lets us handle more complex types like enums
        # and multi-type tuples.
        if "type" in kwargs:
            kwargs["type"] = str

        # Don't pass field action into argparse.
        if "dest" in kwargs:
            kwargs["dest"] = self.prefix + kwargs["dest"]

        kwargs.pop("field")
        kwargs.pop("parent_class")
        kwargs.pop("prefix")
        kwargs.pop("field_action")
        kwargs.pop("name")

        # Note that the name must be passed in as a position argument.
        parser.add_argument(self.get_flag(), **kwargs)

    def get_flag(self) -> str:
        return "--" + (self.prefix + self.name).replace("_", "-")

    @staticmethod
    def make_from_field(
        parent_class: Type,
        field: dataclasses.Field,
        type_from_typevar: Dict[TypeVar, Type],
        default_override: Optional[Any],
    ) -> "ArgumentDefinition":
        """Create an argument definition from a field. Also returns a field action, which
        specifies special instructions for reconstruction."""

        assert field.init, "Field must be in class constructor"

        # Create initial argument.
        arg = ArgumentDefinition(
            prefix="",
            field=field,
            parent_class=parent_class,
            field_action=_no_op_action,
            name=field.name,
            type=field.type,
            default=default_override,
        )

        # Propagate argument through transforms until stable.
        prev_arg = arg

        def _handle_generics(arg: ArgumentDefinition) -> ArgumentDefinition:
            """Handle generic arguments. Note that this needs to be a transform -- if we
            only checked field.type before running transforms, we wouldn't be able to
            handle cases like Optional[T]."""
            if isinstance(arg.type, TypeVar):
                assert arg.type in type_from_typevar, "TypeVar not bounded"
                return dataclasses.replace(
                    arg, type=type_from_typevar[arg.type]  # type:ignore
                )
            else:
                return arg

        while True:
            for transform in [_handle_generics] + _argument_transforms:  # type: ignore
                # Apply transform.
                arg = transform(arg)

            # Stability check.
            if arg == prev_arg:
                break
            prev_arg = arg

        if arg.field_action is _no_op_action and arg.type is not None:
            cast_type = cast(Type, arg.type)
            arg = dataclasses.replace(
                arg,
                field_action=lambda x: _construction.instance_from_string(
                    cast_type,
                    x,
                ),
            )
        elif arg.field_action is _no_op_action:
            assert arg.action in ("store_true", "store_false")

        return arg


# Argument transformations.
# Each transform returns an argument definition and (optionall) a special action for
# reconstruction -- note that a field can only ever have one action.


def _unwrap_final(arg: ArgumentDefinition) -> ArgumentDefinition:
    """Treat Final[T] as just T."""
    if get_origin(arg.type) is Final:
        (typ,) = get_args(arg.type)
        return dataclasses.replace(
            arg,
            type=typ,
        )
    else:
        return arg


def _unwrap_annotated(arg: ArgumentDefinition) -> ArgumentDefinition:
    """Treat Annotated[T, annotation] as just T."""
    if hasattr(arg.type, "__class__") and arg.type.__class__ == _AnnotatedAlias:
        typ = get_origin(arg.type)
        return dataclasses.replace(
            arg,
            type=typ,
        )
    else:
        return arg


def _handle_optionals(arg: ArgumentDefinition) -> ArgumentDefinition:
    """Transform for handling Optional[T] types. Sets default to None and marks arg as
    not required."""
    if get_origin(arg.type) is Union:
        options = set(get_args(arg.type))
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
        # Skip if another handler has already populated the default.
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

    # Populate helptext for boolean flags => don't show default value, which can be
    # confusing.
    docstring_help = _docstrings.get_field_docstring(arg.parent_class, arg.field.name)
    if docstring_help is not None:
        # Note that the percent symbol needs some extra handling in argparse.
        # https://stackoverflow.com/questions/21168120/python-argparse-errors-with-in-help-string
        docstring_help = docstring_help.replace("%", "%%")
        arg = dataclasses.replace(
            arg,
            help=docstring_help,
        )
    else:
        arg = dataclasses.replace(
            arg,
            help="",
        )

    if arg.default is None:
        return dataclasses.replace(
            arg,
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


def _nargs_from_sequences_lists_and_sets(
    arg: ArgumentDefinition,
) -> ArgumentDefinition:
    """Transform for handling Sequence[T] and list types."""
    if get_origin(arg.type) in (
        collections.abc.Sequence,  # different from typing.Sequence!
        list,  # different from typing.List!
        set,  # different from typing.Set!
    ):
        (typ,) = get_args(arg.type)
        container_type = get_origin(arg.type)
        if container_type is collections.abc.Sequence:
            container_type = list

        return dataclasses.replace(
            arg,
            type=typ,
            # `*` is >=0 values, `+` is >=1 values
            # We're going to require at least 1 value; if a user wants to accept no
            # input, they can use Optional[Tuple[...]]
            nargs="+",
            field_action=lambda str_list: container_type(  # type: ignore
                _construction.instance_from_string(typ, x) for x in str_list
            ),
        )
    else:
        return arg


def _nargs_from_tuples(arg: ArgumentDefinition) -> ArgumentDefinition:
    """Transform for handling Tuple[T, T, ...] types."""

    if arg.nargs is None and get_origin(arg.type) is tuple:
        types = get_args(arg.type)
        typeset = set(types)
        typeset_no_ellipsis = typeset - {Ellipsis}

        if typeset_no_ellipsis != typeset:
            # Ellipsis: variable argument counts
            assert (
                len(typeset_no_ellipsis) == 1
            ), "If ellipsis is used, tuples must contain only one type."
            (typ,) = typeset_no_ellipsis

            return dataclasses.replace(
                arg,
                # `*` is >=0 values, `+` is >=1 values.
                # We're going to require at least 1 value; if a user wants to accept no
                # input, they can use Optional[Tuple[...]].
                nargs="+",
                type=typ,
                field_action=lambda str_list: tuple(
                    _construction.instance_from_string(typ, x) for x in str_list
                ),
            )
        else:
            # Tuples with more than one type
            assert arg.metavar is None

            return dataclasses.replace(
                arg,
                nargs=len(types),
                type=str,  # Types will be converted in the dataclass reconstruction step.
                metavar=tuple(
                    t.__name__.upper() if hasattr(t, "__name__") else "X" for t in types
                ),
                # Field action: convert lists of strings to tuples of the correct types.
                field_action=lambda str_list: tuple(
                    _construction.instance_from_string(typ, x)
                    for typ, x in zip(types, str_list)
                ),
            )

    else:
        return arg


def _choices_from_literals(arg: ArgumentDefinition) -> ArgumentDefinition:
    """For literal types, set choices."""
    if get_origin(arg.type) is Literal:
        choices = get_args(arg.type)
        assert (
            len(set(map(type, choices))) == 1
        ), "All choices in literal must have the same type!"
        return dataclasses.replace(
            arg,
            type=type(next(iter(choices))),
            choices=set(map(str, choices)),
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

        return dataclasses.replace(
            arg,
            choices=choices,
            type=str,
            default=None if arg.default is None else arg.default.name,
            field_action=lambda enum_name: arg.type[enum_name],  # type: ignore
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
            # Note that the percent symbol needs some extra handling in argparse.
            # https://stackoverflow.com/questions/21168120/python-argparse-errors-with-in-help-string
            docstring_help = docstring_help.replace("%", "%%")
            help_parts.append(docstring_help)

        if arg.default is not None and hasattr(arg.default, "name"):
            # Special case for enums.
            help_parts.append(f"(default: {arg.default.name})")
        elif not arg.required:
            # General case.
            help_parts.append("(default: %(default)s)")

        return dataclasses.replace(arg, help=" ".join(help_parts))
    else:
        return arg


def _use_type_as_metavar(arg: ArgumentDefinition) -> ArgumentDefinition:
    """Communicate the argument type using the metavar."""
    if hasattr(arg.type, "__name__") and arg.choices is None and arg.metavar is None:
        return dataclasses.replace(
            arg, metavar=arg.type.__name__.upper()  # type: ignore
        )  # type: ignore
    else:
        return arg


_argument_transforms: List[Callable[[ArgumentDefinition], ArgumentDefinition]] = [
    _unwrap_final,
    _unwrap_annotated,
    _handle_optionals,
    _populate_defaults,
    _bool_flags,
    _nargs_from_sequences_lists_and_sets,
    _nargs_from_tuples,
    _choices_from_literals,
    _enums_as_strings,
    _generate_helptext,
    _use_type_as_metavar,
]
