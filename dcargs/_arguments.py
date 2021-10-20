import argparse
import collections.abc
import dataclasses
import enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, TypeVar, Union

from typing_extensions import Final, Literal, _AnnotatedAlias  # Backward compatibility.

from . import _construction, _docstrings, _strings


@dataclasses.dataclass(frozen=True)
class ArgumentDefinition:
    """Options for defining arguments. Contains all necessary arguments for argparse's
    add_argument() method."""

    # Fields that will be populated initially.
    name: str
    field: dataclasses.Field
    parent_class: Type
    type: Optional[Union[Type, TypeVar]]

    # Fields that will be handled by argument transformations.
    required: Optional[bool] = None
    action: Optional[str] = None
    nargs: Optional[Union[int, str]] = None
    default: Optional[Any] = None
    choices: Optional[Set[Any]] = None
    metavar: Optional[str] = None
    help: Optional[str] = None
    dest: Optional[str] = None

    def add_argument(
        self, parser: Union[argparse.ArgumentParser, argparse._ArgumentGroup]
    ) -> None:
        """Add a defined argument to a parser."""
        kwargs = {k: v for k, v in vars(self).items() if v is not None}
        name = "--" + kwargs.pop("name").replace("_", "-")
        kwargs.pop("field")
        kwargs.pop("parent_class")
        parser.add_argument(name, **kwargs)

    def prefix(self, prefix: str) -> "ArgumentDefinition":
        """Prefix an argument's name and destination. Used for nested dataclasses."""
        _strings.NESTED_DATACLASS_DELIMETER
        arg = self
        arg = dataclasses.replace(arg, name=prefix + arg.name)
        if arg.dest is not None:
            arg = dataclasses.replace(arg, dest=prefix + arg.dest)
        return arg

    @staticmethod
    def make_from_field(
        parent_class: Type,
        field: dataclasses.Field,
        type_from_typevar: Dict[TypeVar, Type],
    ) -> Tuple["ArgumentDefinition", _construction.FieldRole]:
        """Create an argument definition from a field. Also returns a field role, which
        specifies special instructions for reconstruction."""

        assert field.init, "Field must be in class constructor"

        # Create initial argument.
        arg = ArgumentDefinition(
            name=field.name,
            field=field,
            parent_class=parent_class,
            type=field.type,
        )

        # Propagate argument through transforms until stable.
        prev_arg = arg
        role: _construction.FieldRole = _construction.FieldRole.VANILLA_FIELD

        def _handle_generics(arg: ArgumentDefinition) -> _ArgumentTransformOutput:
            if isinstance(arg.type, TypeVar):
                assert arg.type in type_from_typevar, "TypeVar not bounded"
                return (
                    dataclasses.replace(
                        arg, type=type_from_typevar[arg.type]  # type:ignore
                    ),
                    None,
                )
            else:
                return arg, None

        while True:
            for transform in [_handle_generics] + _argument_transforms:  # type: ignore
                # Apply transform.
                arg, new_role = transform(arg)

                # Update field role.
                if new_role is not None:
                    assert (
                        role == _construction.FieldRole.VANILLA_FIELD
                    ), "Something went wrong -- only one field role can be specified per argument!"
                    role = new_role

            # Stability check.
            if arg == prev_arg:
                break
            prev_arg = arg
        return arg, role


# Argument transformations.
# Each transform returns an argument definition and (optionall) a special role for
# reconstruction -- note that a field can only ever have one role.

_ArgumentTransformOutput = Tuple[ArgumentDefinition, Optional[_construction.FieldRole]]


def _unwrap_final(arg: ArgumentDefinition) -> _ArgumentTransformOutput:
    """Treat Final[T] as just T."""
    if hasattr(arg.type, "__origin__") and arg.type.__origin__ is Final:  # type: ignore
        (typ,) = arg.type.__args__  # type: ignore
        return (
            dataclasses.replace(
                arg,
                type=typ,
            ),
            None,
        )
    else:
        return arg, None


def _unwrap_annotated(arg: ArgumentDefinition) -> _ArgumentTransformOutput:
    """Treat Annotated[T, annotation] as just T."""
    if hasattr(arg.type, "__class__") and arg.type.__class__ == _AnnotatedAlias:
        typ = arg.type.__origin__  # type: ignore
        return (
            dataclasses.replace(
                arg,
                type=typ,
            ),
            None,
        )
    else:
        return arg, None


def _handle_optionals(arg: ArgumentDefinition) -> _ArgumentTransformOutput:
    """Transform for handling Optional[T] types. Sets default to None and marks arg as
    not required."""
    if hasattr(arg.type, "__origin__") and arg.type.__origin__ is Union:  # type: ignore
        options = set(arg.type.__args__)  # type: ignore
        assert (
            len(options) == 2 and type(None) in options
        ), "Union must be either over dataclasses (for subparsers) or Optional"
        (typ,) = options - {type(None)}
        required = False
        return (
            dataclasses.replace(
                arg,
                type=typ,
                required=required,
            ),
            None,
        )
    else:
        return arg, None


def _populate_defaults(arg: ArgumentDefinition) -> _ArgumentTransformOutput:
    """Populate default values."""
    if arg.default is not None:
        # Skip if another handler has already populated the default.
        return arg, None

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

    return dataclasses.replace(arg, default=default, required=required), None


def _bool_flags(arg: ArgumentDefinition) -> _ArgumentTransformOutput:
    """For booleans, we use a `store_true` action."""
    if arg.type != bool:
        return arg, None

    if arg.default is None:
        return (
            dataclasses.replace(
                arg,
                type=_strings.bool_from_string,  # type: ignore
                metavar="{True,False}",
            ),
            None,
        )
    elif arg.default is False:
        return (
            dataclasses.replace(
                arg,
                action="store_true",
                type=None,
            ),
            None,
        )
    elif arg.default is True:
        return (
            dataclasses.replace(
                arg,
                dest=arg.name,
                name="no_" + arg.name,
                action="store_false",
                type=None,
            ),
            None,
        )
    else:
        assert False, "Invalid default"


def _nargs_from_sequences_and_lists(
    arg: ArgumentDefinition,
) -> _ArgumentTransformOutput:
    """Transform for handling Sequence[T] and list types."""
    if hasattr(arg.type, "__origin__") and arg.type.__origin__ in (  # type: ignore
        collections.abc.Sequence,  # different from typing.Sequence!
        list,  # different from typing.List!
    ):
        assert len(arg.type.__args__) == 1  # type: ignore
        (typ,) = arg.type.__args__  # type: ignore

        return (
            dataclasses.replace(
                arg,
                type=typ,
                # `*` is >=0 values, `+` is >=1 values
                # We're going to require at least 1 value; if a user wants to accept no
                # input, they can use Optional[Tuple[...]]
                nargs="+",
            ),
            None,
        )
    else:
        return arg, None


def _nargs_from_tuples(arg: ArgumentDefinition) -> _ArgumentTransformOutput:
    """Transform for handling Tuple[T, T, ...] types."""
    if hasattr(arg.type, "__origin__") and arg.type.__origin__ == tuple:  # type: ignore
        argset = set(arg.type.__args__)  # type: ignore
        argset_no_ellipsis = argset - {Ellipsis}  #
        assert len(argset_no_ellipsis) == 1, "Tuples must be of a single type!"

        if argset != argset_no_ellipsis:
            # `*` is >=0 values, `+` is >=1 values.
            # We're going to require at least 1 value; if a user wants to accept no
            # input, they can use Optional[Tuple[...]].
            nargs = "+"
        else:
            nargs = len(arg.type.__args__)  # type: ignore
        (typ,) = argset_no_ellipsis

        return (
            dataclasses.replace(
                arg,
                nargs=nargs,
                type=typ,
            ),
            _construction.FieldRole.TUPLE,
        )
    else:
        return arg, None


def _choices_from_literals(arg: ArgumentDefinition) -> _ArgumentTransformOutput:
    """For literal types, set choices."""
    if hasattr(arg.type, "__origin__") and arg.type.__origin__ is Literal:  # type: ignore
        choices = set(arg.type.__args__)  # type: ignore
        assert (
            len(set(map(type, choices))) == 1
        ), "All choices in literal must have the same type!"
        return (
            dataclasses.replace(
                arg,
                type=type(arg.type.__args__[0]),  # type: ignore
                choices=choices,
            ),
            None,
        )
    else:
        return arg, None


def _enums_as_strings(arg: ArgumentDefinition) -> _ArgumentTransformOutput:
    """For enums, use string representations."""
    if isinstance(arg.type, type) and issubclass(arg.type, enum.Enum):
        if arg.choices is None:
            choices = set(x.name for x in arg.type)
        else:
            choices = set(x.name for x in arg.choices)

        return (
            dataclasses.replace(
                arg,
                choices=choices,
                type=str,
                default=None if arg.default is None else arg.default.name,
            ),
            _construction.FieldRole.ENUM,
        )
    else:
        return arg, None


def _generate_helptext(arg: ArgumentDefinition) -> _ArgumentTransformOutput:
    """Generate helptext from docstring and argument name."""
    if arg.help is None:
        help_parts = []
        docstring_help = _docstrings.get_field_docstring(
            arg.parent_class, arg.field.name
        )
        if docstring_help is not None:
            help_parts.append(docstring_help)

        if arg.default is not None and hasattr(arg.default, "name"):
            # Special case for enums.
            help_parts.append(f"(default: {arg.default.name})")
        elif arg.default is not None:
            # General case.
            help_parts.append("(default: %(default)s)")

        return dataclasses.replace(arg, help=" ".join(help_parts)), None
    else:
        return arg, None


def _use_type_as_metavar(arg: ArgumentDefinition) -> _ArgumentTransformOutput:
    """Communicate the argument type using the metavar."""
    if hasattr(arg.type, "__name__") and arg.choices is None and arg.metavar is None:
        return (
            dataclasses.replace(arg, metavar=arg.type.__name__.upper()),  # type: ignore
            None,
        )
    else:
        return arg, None


_argument_transforms: List[Callable[[ArgumentDefinition], _ArgumentTransformOutput]] = [
    _unwrap_final,
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
