import dataclasses
from typing import Any, Optional

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
                NestedTypeA, subcommand("b", ...)
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
    # TODO - add prefix_name: bool


def arg(
    *,
    name: Optional[str] = None,
    metavar: Optional[str] = None,
    help: Optional[str] = None,
) -> Any:
    """Returns a metadata object for configuring arguments with `typing.Annotated`.
    Useful for aesthetics.

    Usage:
    ```python
    x: Annotated[int, tyro.conf.arg(...)]
    ```
    """
    return _ArgConfiguration(name=name, metavar=metavar, help=help)
