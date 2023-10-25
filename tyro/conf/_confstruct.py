import dataclasses
from typing import Any, Callable, Optional, Type, Union, overload

from .._fields import MISSING_NONPROP


@dataclasses.dataclass(frozen=True)
class _SubcommandConfiguration:
    name: Optional[str]
    default: Any
    description: Optional[str]
    prefix_name: bool

    def __hash__(self) -> int:
        return object.__hash__(self)


def subcommand(
    name: Optional[str] = None,
    *,
    default: Any = MISSING_NONPROP,
    description: Optional[str] = None,
    prefix_name: bool = True,
) -> Any:
    """Returns a metadata object for configuring subcommands with `typing.Annotated`.
    Useful for aesthetics.

    Consider the standard approach for creating subcommands:

    ```python
    tyro.cli(
        Union[NestedTypeA, NestedTypeB]
    )
    ```

    This will create two subcommands: `nested-type-a` and `nested-type-b`.

    Annotating each type with `tyro.metadata.subcommand()` allows us to override for
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
    """
    return _SubcommandConfiguration(name, default, description, prefix_name)


@dataclasses.dataclass(frozen=True)
class _ArgConfiguration:
    name: Optional[str]
    metavar: Optional[str]
    help: Optional[str]
    prefix_name: bool
    constructor_factory: Optional[Callable[[], Union[Type, Callable]]]


@overload
def arg(
    *,
    name: Optional[str] = None,
    metavar: Optional[str] = None,
    help: Optional[str] = None,
    prefix_name: bool = True,
    constructor: Optional[Union[Type, Callable]] = None,
    constructor_factory: None = None,
) -> Any:
    ...


@overload
def arg(
    *,
    name: Optional[str] = None,
    metavar: Optional[str] = None,
    help: Optional[str] = None,
    prefix_name: bool = True,
    constructor: None = None,
    constructor_factory: Optional[Callable[[], Union[Type, Callable]]] = None,
) -> Any:
    ...


def arg(
    *,
    name: Optional[str] = None,
    metavar: Optional[str] = None,
    help: Optional[str] = None,
    prefix_name: bool = True,
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
        prefix_name: Whether or not to prefix the name of the argument based on where
            it is in a nested structure.
        constructor: A constructor type or function. This should either be (a) a subtype
            of an argument's annotated type, or (b) a function that returns an instance of
            the annotated type. This will be used in place of the argument's type for
            parsing arguments. No validation is done.
        constructor_factory: A function that returns a constructor type or function.
            Useful when the constructor isn't immediately available.
    """
    assert not (
        constructor is not None and constructor_factory is not None
    ), "`constructor` and `constructor_factory` cannot both be set."
    return _ArgConfiguration(
        name=name,
        metavar=metavar,
        help=help,
        prefix_name=prefix_name,
        constructor_factory=constructor_factory
        if constructor is None
        else lambda: constructor,
    )
