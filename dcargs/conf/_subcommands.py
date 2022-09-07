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
    This is useful but can make code harder to read, so usage is discouraged.

    Consider the standard approach for creating subcommands:

    ```python
    dcargs.cli(
        Union[NestedTypeA, NestedTypeB]
    )
    ```

    This will create two subcommands: `nested-type-a` and `nested-type-b`.

    Annotating each type with `dcargs.metadata.subcommand()` allows us to override for
    each subcommand the (a) name, (b) defaults, (c) helptext, and (d) whether to prefix
    the name or not.

    ```python
    dcargs.cli(
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
