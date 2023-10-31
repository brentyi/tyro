import dataclasses
from typing import Any, Callable, Optional, Sequence, Tuple, Type, Union, overload

from .._fields import MISSING_NONPROP


@dataclasses.dataclass(frozen=True)
class _SubcommandConfiguration:
    name: Optional[str]
    default: Any
    description: Optional[str]
    prefix_name: bool
    constructor_factory: Optional[Callable[[], Union[Type, Callable]]]

    def __hash__(self) -> int:
        return object.__hash__(self)


@overload
def subcommand(
    name: Optional[str] = None,
    *,
    default: Any = MISSING_NONPROP,
    description: Optional[str] = None,
    prefix_name: bool = True,
    constructor: None = None,
    constructor_factory: Optional[Callable[[], Union[Type, Callable]]] = None,
) -> Any:
    ...


@overload
def subcommand(
    name: Optional[str] = None,
    *,
    default: Any = MISSING_NONPROP,
    description: Optional[str] = None,
    prefix_name: bool = True,
    constructor: Optional[Union[Type, Callable]] = None,
    constructor_factory: None = None,
) -> Any:
    ...


def subcommand(
    name: Optional[str] = None,
    *,
    default: Any = MISSING_NONPROP,
    description: Optional[str] = None,
    prefix_name: bool = True,
    constructor: Optional[Union[Type, Callable]] = None,
    constructor_factory: Optional[Callable[[], Union[Type, Callable]]] = None,
) -> Any:
    assert not (
        constructor is not None and constructor_factory is not None
    ), "`constructor` and `constructor_factory` cannot both be set."
    """Returns a metadata object for configuring subcommands with `typing.Annotated`.
    Useful for aesthetics.

    Consider the standard approach for creating subcommands:

    ```python
    tyro.cli(
        Union[NestedTypeA, NestedTypeB]
    )
    ```

    This will create two subcommands: `nested-type-a` and `nested-type-b`.

    Annotating each type with `tyro.conf.subcommand()` allows us to override for
    each subcommand the (a) name, (b) defaults, (c) helptext, and (d) whether to prefix
    the name or not.

    ```python
    tyro.cli(
        Union[
            Annotated[
                NestedTypeA, subcommand("a", ...)
            ],
            Annotated[
                NestedTypeB, subcommand("b", ...)
            ],
        ]
    )
    ```

    Arguments:
        name: The name of the subcommand in the CLI.
        default: A default value for the subcommand, for struct-like types. (eg
             dataclasses)
        description: Description of this option to use in the helptext. Defaults to
            docstring.
        prefix_name: Whether to prefix the name of the subcommand based on where it
            is in a nested structure.
        constructor: A constructor type or function. This should either be (a) a subtype
            of an argument's annotated type, or (b) a function with type-annotated
            inputs that returns an instance of the annotated type. This will be used in
            place of the argument's type for parsing arguments. No validation is done.
        constructor_factory: A function that returns a constructor type or function.
            Useful when the constructor isn't immediately available.
    """
    return _SubcommandConfiguration(
        name,
        default,
        description,
        prefix_name,
        constructor_factory=constructor_factory
        if constructor is None
        else lambda: constructor,
    )


@dataclasses.dataclass(frozen=True)
class _ArgConfiguration:
    # These are all optional by default in order to support multiple tyro.conf.arg()
    # annotations. A None value means "don't overwrite the current value".
    name: Optional[str]
    metavar: Optional[str]
    help: Optional[str]
    aliases: Optional[Tuple[str, ...]]
    prefix_name: Optional[bool]
    constructor_factory: Optional[Callable[[], Union[Type, Callable]]]


@overload
def arg(
    *,
    name: Optional[str] = None,
    metavar: Optional[str] = None,
    help: Optional[str] = None,
    aliases: Optional[Sequence[str]] = None,
    prefix_name: Optional[bool] = None,
    constructor: None = None,
    constructor_factory: Optional[Callable[[], Union[Type, Callable]]] = None,
) -> Any:
    ...


@overload
def arg(
    *,
    name: Optional[str] = None,
    metavar: Optional[str] = None,
    help: Optional[str] = None,
    aliases: Optional[Sequence[str]] = None,
    prefix_name: Optional[bool] = None,
    constructor: Optional[Union[Type, Callable]] = None,
    constructor_factory: None = None,
) -> Any:
    ...


def arg(
    *,
    name: Optional[str] = None,
    metavar: Optional[str] = None,
    help: Optional[str] = None,
    aliases: Optional[Sequence[str]] = None,
    prefix_name: Optional[bool] = None,
    constructor: Optional[Union[Type, Callable]] = None,
    constructor_factory: Optional[Callable[[], Union[Type, Callable]]] = None,
) -> Any:
    """Returns a metadata object for fine-grained argument configuration with
    `typing.Annotated`. Should typically not be required.
    ```python
    x: Annotated[int, tyro.conf.arg(...)]
    ```

    Arguments:
        name: A new name for the argument.
        metavar: Argument name in usage messages. The type is used by default.
        help: Helptext for this argument. The docstring is used by default.
        aliases: Aliases for this argument. All strings in the sequence should start
            with a hyphen (-). Aliases will _not_ currently be prefixed in a nested
            structure, and are not supported for positional arguments.
        prefix_name: Whether or not to prefix the name of the argument based on where
            it is in a nested structure. Arguments are prefixed by default.
        constructor: A constructor type or function. This should either be (a) a subtype
            of an argument's annotated type, or (b) a function with type-annotated
            inputs that returns an instance of the annotated type. This will be used in
            place of the argument's type for parsing arguments. No validation is done.
        constructor_factory: A function that returns a constructor type or function.
            Useful when the constructor isn't immediately available.

    Returns:
        Object to attach via `typing.Annotated[]`.
    """
    assert not (
        constructor is not None and constructor_factory is not None
    ), "`constructor` and `constructor_factory` cannot both be set."

    if aliases is not None:
        for alias in aliases:
            assert alias.startswith("-"), "Argument alias needs to start with a hyphen!"

    return _ArgConfiguration(
        name=name,
        metavar=metavar,
        help=help,
        aliases=tuple(aliases) if aliases is not None else None,
        prefix_name=prefix_name,
        constructor_factory=constructor_factory
        if constructor is None
        else lambda: constructor,
    )
