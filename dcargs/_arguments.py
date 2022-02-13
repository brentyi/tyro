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

from . import _docstrings, _strings

T = TypeVar("T")


def instance_from_string(typ: Type, arg: str) -> T:
    """Given a type and and a string from the command-line, reconstruct an object. Not
    intended to deal with containers; these are handled in the argument
    transformations.

    This is intended to replace all calls to `type(string)`, which can cause unexpected
    behavior. As an example, note that the following argparse code will always print
    `True`, because `bool("True") == bool("False") == bool("0") == True`.
    ```
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--flag", type=bool)

    print(parser.parse_args().flag)
    ```
    """
    assert len(get_args(typ)) == 0, f"Type {typ} cannot be instantiated."
    if typ is bool:
        return _strings.bool_from_string(arg)  # type: ignore
    else:
        return typ(arg)  # type: ignore


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
    #
    # There are 3 options:
    field_action: Union[
        # Most standard fields: these are converted from strings from the CLI.
        Callable[[str], Any],
        # Sequence fields! This should be used whenever argparse's `nargs` field is set.
        Callable[[List[str]], Any],
        # Special case: the only time that argparse doesn't give us a string is when the
        # argument action is set to `store_true` or `store_false`. In this case, we get
        # a bool directly, and the field action can be a no-op.
        Callable[[bool], bool],
    ]

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
        kwargs.pop("field_action")
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
        default_override: Optional[Any],
    ) -> "ArgumentDefinition":
        """Create an argument definition from a field. Also returns a field action, which
        specifies special instructions for reconstruction."""

        assert field.init, "Field must be in class constructor"

        # The default field action: this converts a string from argparse to the desired
        # type of the argument.
        def default_field_action(x: str) -> Any:
            return instance_from_string(cast(Type, arg.type), x)

        # Create initial argument.
        arg = ArgumentDefinition(
            prefix="",
            field=field,
            parent_class=parent_class,
            field_action=default_field_action,
            name=field.name,
            type=field.type,
            default=default_override,
        )

        # Propagate argument through transforms until stable.
        prev_arg = arg
        argument_transforms = _get_argument_transforms(type_from_typevar)
        while True:
            for transform in argument_transforms:  # type: ignore
                # Apply transform.
                arg = transform(arg)

            # Stability check.
            if arg == prev_arg:
                break
            prev_arg = arg

        return arg


def _get_argument_transforms(
    type_from_typevar: Dict[TypeVar, Type]
) -> List[Callable[[ArgumentDefinition], ArgumentDefinition]]:
    """Get a list of argument transformations."""

    def resolve_typevars(typ: Union[Type, TypeVar]) -> Type:
        return type_from_typevar.get(cast(TypeVar, typ), cast(Type, typ))

    # All transforms should start with `transform_`.

    def transform_resolve_arg_typevars(arg: ArgumentDefinition) -> ArgumentDefinition:
        if arg.type is not None:
            return dataclasses.replace(
                arg,
                type=resolve_typevars(arg.type),
            )
        return arg

    def transform_unwrap_final(arg: ArgumentDefinition) -> ArgumentDefinition:
        """Treat Final[T] as just T."""
        if get_origin(arg.type) is Final:
            (typ,) = get_args(arg.type)
            return dataclasses.replace(
                arg,
                type=typ,
            )
        else:
            return arg

    def transform_unwrap_annotated(arg: ArgumentDefinition) -> ArgumentDefinition:
        """Treat Annotated[T, annotation] as just T."""
        if hasattr(arg.type, "__class__") and arg.type.__class__ == _AnnotatedAlias:
            typ = get_origin(arg.type)
            return dataclasses.replace(
                arg,
                type=typ,
            )
        else:
            return arg

    def transform_handle_optionals(arg: ArgumentDefinition) -> ArgumentDefinition:
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

    def transform_populate_defaults(arg: ArgumentDefinition) -> ArgumentDefinition:
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

    def transform_booleans(arg: ArgumentDefinition) -> ArgumentDefinition:
        """Set choices or actions for booleans."""
        if arg.type != bool or arg.choices is not None:
            return arg

        if arg.default is None:
            # If no default is passed in, the user must explicitly choose between `True`
            # and `False`.
            return dataclasses.replace(
                arg,
                choices=(True, False),
            )
        elif arg.default is False:
            # Default `False` => --flag passed in flips to `True`.
            return dataclasses.replace(
                arg,
                action="store_true",
                type=None,
                field_action=lambda x: x,  # argparse will directly give us a bool!
            )
        elif arg.default is True:
            # Default `True` => --no-flag passed in flips to `False`.
            return dataclasses.replace(
                arg,
                dest=arg.name,
                name="no_" + arg.name,
                action="store_false",
                type=None,
                field_action=lambda x: x,  # argparse will directly give us a bool!
            )
        else:
            assert False, "Invalid default"

    def transform_nargs_from_sequences_lists_and_sets(
        arg: ArgumentDefinition,
    ) -> ArgumentDefinition:
        """Transform for handling Sequence[T] and list types."""
        if get_origin(arg.type) in (
            collections.abc.Sequence,  # different from typing.Sequence!
            list,  # different from typing.List!
            set,  # different from typing.Set!
        ):
            assert arg.nargs is None, "Sequence types cannot be nested."
            (typ,) = map(resolve_typevars, get_args(arg.type))
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
                    instance_from_string(typ, x) for x in str_list
                ),
            )
        else:
            return arg

    def transform_nargs_from_tuples(arg: ArgumentDefinition) -> ArgumentDefinition:
        """Transform for handling Tuple[T, T, ...] types."""

        if arg.nargs is None and get_origin(arg.type) is tuple:
            assert arg.nargs is None, "Sequence types cannot be nested."
            types = tuple(map(resolve_typevars, get_args(arg.type)))
            typeset = set(types)  # Note that sets are unordered.
            typeset_no_ellipsis = typeset - {Ellipsis}  # type: ignore

            if typeset_no_ellipsis != typeset:
                # Ellipsis: variable argument counts.
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
                        instance_from_string(typ, x) for x in str_list
                    ),
                )
            else:
                # Tuples with more than one type.
                assert arg.metavar is None

                return dataclasses.replace(
                    arg,
                    nargs=len(types),
                    type=str,  # Types are converted in the field action.
                    metavar=tuple(
                        t.__name__.upper() if hasattr(t, "__name__") else "X"
                        for t in types
                    ),
                    # Field action: convert lists of strings to tuples of the correct types.
                    field_action=lambda str_list: tuple(
                        instance_from_string(typ, x) for typ, x in zip(types, str_list)
                    ),
                )

        else:
            return arg

    def transform_choices_from_literals(arg: ArgumentDefinition) -> ArgumentDefinition:
        """For literal types, set choices."""
        if get_origin(arg.type) is Literal:
            choices = get_args(arg.type)
            typ = type(next(iter(choices)))

            assert typ not in (
                list,
                tuple,
                set,
            ), "Containers not supported in literals."
            assert all(
                map(lambda c: type(c) == typ, choices)
            ), "All choices in literal must have the same type!"

            return dataclasses.replace(
                arg,
                type=typ,
                choices=choices,
            )
        else:
            return arg

    def transform_enums_as_strings(arg: ArgumentDefinition) -> ArgumentDefinition:
        """For enums, use string representations."""
        if isinstance(arg.type, type) and issubclass(arg.type, enum.Enum):
            if arg.choices is None:
                # We use a list and not a set to preserve ordering.
                choices = list(x.name for x in arg.type)
            else:
                # `arg.choices` is set; this occurs when we have enums in a literal
                # type.
                choices = list(x.name for x in arg.choices)
            assert len(choices) == len(set(choices))

            return dataclasses.replace(
                arg,
                choices=choices,
                type=str,
                default=None if arg.default is None else arg.default.name,
                field_action=lambda enum_name: arg.type[enum_name],  # type: ignore
            )
        else:
            return arg

    def transform_generate_helptext(arg: ArgumentDefinition) -> ArgumentDefinition:
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

            if arg.action is not None:
                # Don't show defaults for boolean flags.
                assert arg.action in ("store_true", "store_false")
            elif arg.default is not None and hasattr(arg.default, "name"):
                # Special case for enums.
                help_parts.append(f"(default: {arg.default.name})")
            elif not arg.required:
                # General case.
                help_parts.append("(default: %(default)s)")

            return dataclasses.replace(arg, help=" ".join(help_parts))
        else:
            return arg

    def transform_use_type_as_metavar(arg: ArgumentDefinition) -> ArgumentDefinition:
        """Communicate the argument type using the metavar."""
        if (
            hasattr(arg.type, "__name__")
            # Don't generate metavar if target is still wrapping something, eg
            # Optional[int] will have 1 arg.
            and len(get_args(arg.type)) == 0
            # If choices is set, they'll be used by default.
            and arg.choices is None
            # Don't generate metavar if one already exists.
            and arg.metavar is None
        ):
            return dataclasses.replace(
                arg, metavar=arg.type.__name__.upper()  # type: ignore
            )  # type: ignore
        else:
            return arg

    return [v for k, v in locals().items() if k.startswith("transform_")]
