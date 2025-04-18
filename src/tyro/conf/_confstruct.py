from __future__ import annotations

import dataclasses
from typing import Any, Callable, TypeVar, overload

from .._singleton import MISSING_NONPROP

T = TypeVar("T")


@dataclasses.dataclass(frozen=True)
class _SubcommandConfig:
    name: str | None
    default: Any
    description: str | None
    prefix_name: bool
    constructor_factory: Callable[[], type | Callable[..., Any]] | None

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
    constructor_factory: Callable[[], type | Callable[..., Any]] | None = None,
) -> Any: ...


@overload
def subcommand(
    name: str | None = None,
    *,
    default: Any = MISSING_NONPROP,
    description: str | None = None,
    prefix_name: bool = True,
    constructor: type | Callable[..., Any] | None = None,
    constructor_factory: None = None,
) -> Any: ...


def subcommand(
    name: str | None = None,
    *,
    default: Any = MISSING_NONPROP,
    description: str | None = None,
    prefix_name: bool = True,
    constructor: type | Callable[..., Any] | None = None,
    constructor_factory: Callable[[], type | Callable[..., Any]] | None = None,
) -> Any:
    """Configure subcommand behavior for Union types in the CLI.

    When tyro encounters a Union type over structures, it creates subcommands in the
    CLI. The `subcommand()` function allows you to customize the appearance and behavior
    of these subcommands.

    Example::

        from dataclasses import dataclass
        from typing import Annotated, Union
        import tyro

        @dataclass
        class TrainConfig:
            learning_rate: float = 0.01

        @dataclass
        class EvalConfig:
            checkpoint_path: str

        @dataclass
        class MainConfig:
            # Customized subcommands:
            mode: Union[
                Annotated[TrainConfig, tyro.conf.subcommand("train")],
                Annotated[EvalConfig, tyro.conf.subcommand("evaluate")]
            ]

        # CLI usage: python script.py mode:train --mode.learning-rate 0.02

    If a default value is provided both via `subcommand(default=...)` and in the field
    definition itself (`field = default`), the field default will take precedence.

    Args:
        name: Custom name for the subcommand in the CLI.
        default: Default instance to use for this subcommand.
        description: Custom helptext for this subcommand.
        prefix_name: Whether to include the parent field name as a prefix in the subcommand
            name (default: True).
        constructor: Custom constructor type or function for parsing arguments.
        constructor_factory: Function that returns a constructor type for parsing arguments
            (cannot be used with constructor).

    Returns:
        A configuration object that should be attached to a type using `Annotated[]`.
    """
    assert not (constructor is not None and constructor_factory is not None), (
        "`constructor` and `constructor_factory` cannot both be set."
    )
    return _SubcommandConfig(
        name,
        default,
        description,
        prefix_name,
        constructor_factory=(
            constructor_factory if constructor is None else lambda: constructor
        ),
    )


@dataclasses.dataclass(frozen=True)
class _ArgConfig:
    name: str | None
    metavar: str | None
    help: str | None
    help_behavior_hint: str | Callable[[str], str] | None
    aliases: tuple[str, ...] | None
    prefix_name: bool | None
    constructor_factory: Callable[[], type | Callable[..., Any]] | None
    default: Any = MISSING_NONPROP


@overload
def arg(
    *,
    name: str | None = None,
    metavar: str | None = None,
    help: str | None = None,
    help_behavior_hint: str | Callable[[str], str] | None = None,
    aliases: tuple[str, ...] | list[str] | None = None,
    prefix_name: bool | None = None,
    constructor: None = None,
    constructor_factory: Callable[[], type | Callable[..., Any]] | None = None,
    default: Any = MISSING_NONPROP,
) -> Any: ...


@overload
def arg(
    *,
    name: str | None = None,
    metavar: str | None = None,
    help: str | None = None,
    help_behavior_hint: str | Callable[[str], str] | None = None,
    aliases: tuple[str, ...] | list[str] | None = None,
    prefix_name: bool | None = None,
    constructor: type | Callable[..., Any] | None = None,
    constructor_factory: None = None,
    default: Any = MISSING_NONPROP,
) -> Any: ...


def arg(
    *,
    name: str | None = None,
    metavar: str | None = None,
    help: str | None = None,
    help_behavior_hint: str | Callable[[str], str] | None = None,
    aliases: tuple[str, ...] | list[str] | None = None,
    prefix_name: bool | None = None,
    constructor: type | Callable[..., Any] | None = None,
    constructor_factory: Callable[[], type | Callable[..., Any]] | None = None,
    default: Any = MISSING_NONPROP,
) -> Any:
    """Provides fine-grained control over individual CLI argument properties.

    The `arg()` function allows you to customize how individual arguments appear and
    behave in the command-line interface. This provides more control than relying on
    the automatic argument generation.

    Example::

        from dataclasses import dataclass
        from typing import Annotated
        import tyro

        @dataclass
        class Config:
            # Default argument appearance
            regular_option: int = 1

            # Customized argument
            custom_option: Annotated[
                str,
                tyro.conf.arg(
                    name="opt",                     # Shorter name
                    help="Custom help message",     # Override docstring
                    aliases=("-o", "--short-opt"),  # Alternative flags
                    metavar="VALUE"                 # Display in help
                )
            ] = "default"

        # Usage:
        # python script.py --regular-option 5 --opt custom_value
        # python script.py --regular-option 5 -o custom_value

    The `arg()` function should be used at the root level of annotations and not
    nested within container types like lists.

    Args:
        name: A custom name for the argument in the CLI.
        metavar: Argument placeholder shown in usage messages. The type is used by default.
        help: Custom helptext for this argument. The docstring is used by default.
        help_behavior_hint: Override the highlighted hint text that follows the helptext.
            This is typically used for hints like "(default: XXX)" or "(optional)".
            You can provide either a string or a lambda function that takes a formatted
            default value as input.
        aliases: Alternative flag names for this argument. All strings must start
            with a hyphen (-). Aliases are not prefixed in nested structures and are
            not supported for positional arguments.
        prefix_name: Controls whether to prefix the argument name based on its position
            in a nested structure. Arguments are prefixed by default.
        constructor: A custom constructor type or function to use in place of the
            argument's type for parsing. See :mod:`tyro.constructors` for more details.
        constructor_factory: A function that returns a constructor type for parsing.
            This cannot be used together with the constructor parameter.
        default: Default value for the argument. This will be used only if the field
            does not have a default value. The field default takes precedence.

    Returns:
        A configuration object that should be attached to a type using `Annotated[]`.
    """
    assert not (constructor is not None and constructor_factory is not None), (
        "`constructor` and `constructor_factory` cannot both be set."
    )

    if aliases is not None:
        for alias in aliases:
            assert alias.startswith("-"), "Argument alias needs to start with a hyphen!"

    return _ArgConfig(
        name=name,
        metavar=metavar,
        help=help,
        help_behavior_hint=help_behavior_hint,
        aliases=tuple(aliases) if aliases is not None else None,
        prefix_name=prefix_name,
        constructor_factory=(
            constructor_factory if constructor is None else lambda: constructor
        ),
        default=default,
    )
