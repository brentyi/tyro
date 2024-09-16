from __future__ import annotations

import dataclasses
from typing import Any, Callable, Sequence, overload

from .._fields import MISSING_NONPROP


@dataclasses.dataclass(frozen=True)
class _SubcommandConfiguration:
    name: str | None
    default: Any
    description: str | None
    prefix_name: bool
    constructor_factory: Callable[[], type | Callable] | None

    def __hash__(self) -> int:
        return object.__hash__(self)


@overload
def subcommand(
    name: str | None = None,
    *,
    default: Any = MISSING_NONPROP,
    description: str | None = None,
    prefix_name: bool = True,
    constructor: None = None,
    constructor_factory: Callable[[], type | Callable] | None = None,
) -> Any: ...


@overload
def subcommand(
    name: str | None = None,
    *,
    default: Any = MISSING_NONPROP,
    description: str | None = None,
    prefix_name: bool = True,
    constructor: type | Callable | None = None,
    constructor_factory: None = None,
) -> Any: ...


def subcommand(
    name: str | None = None,
    *,
    default: Any = MISSING_NONPROP,
    description: str | None = None,
    prefix_name: bool = True,
    constructor: type | Callable | None = None,
    constructor_factory: Callable[[], type | Callable] | None = None,
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
    assert not (
        constructor is not None and constructor_factory is not None
    ), "`constructor` and `constructor_factory` cannot both be set."
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
    name: str | None
    metavar: str | None
    help: str | None
    help_behavior_hint: str | Callable[[str], str] | None
    aliases: tuple[str, ...] | None
    prefix_name: bool | None
    constructor_factory: Callable[[], type | Callable] | None


@overload
def arg(
    *,
    name: str | None = None,
    metavar: str | None = None,
    help: str | None = None,
    help_behavior_hint: str | Callable[[str], str] | None = None,
    aliases: Sequence[str] | None = None,
    prefix_name: bool | None = None,
    constructor: None = None,
    constructor_factory: Callable[[], type | Callable] | None = None,
) -> Any: ...


@overload
def arg(
    *,
    name: str | None = None,
    metavar: str | None = None,
    help: str | None = None,
    help_behavior_hint: str | Callable[[str], str] | None = None,
    aliases: Sequence[str] | None = None,
    prefix_name: bool | None = None,
    constructor: type | Callable | None = None,
    constructor_factory: None = None,
) -> Any: ...


def arg(
    *,
    name: str | None = None,
    metavar: str | None = None,
    help: str | None = None,
    help_behavior_hint: str | Callable[[str], str] | None = None,
    aliases: Sequence[str] | None = None,
    prefix_name: bool | None = None,
    constructor: type | Callable | None = None,
    constructor_factory: Callable[[], type | Callable] | None = None,
) -> Any:
    """Returns a metadata object for fine-grained argument configuration with
    `typing.Annotated`. Should typically not be required.

    We support using `arg()` at the root of arguments. For example:
    ```python
    x: Annotated[int, tyro.conf.arg(...)]
    ```

    Nesting `arg()` within other types is generally not supported:
    ```python
    # Not supported.
    x: tuple[Annotated[int, tyro.conf.arg(...)], ...]
    ```

    Arguments:
        name: A new name for the argument in the CLI.
        metavar: Argument name in usage messages. The type is used by default.
        help: Override helptext for this argument. The docstring is used by default.
        help_behavior_hint: Override highlighted text that follows the helptext.
            Typically used for behavior hints like the `(default: XXX)` or
            `(optional)`. Can either be a string or a lambda function whose
            input is a formatted default value.
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
        help_behavior_hint=help_behavior_hint,
        aliases=tuple(aliases) if aliases is not None else None,
        prefix_name=prefix_name,
        constructor_factory=constructor_factory
        if constructor is None
        else lambda: constructor,
    )
