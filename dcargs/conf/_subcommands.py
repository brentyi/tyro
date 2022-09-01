import dataclasses
from typing import Any, Optional

from .._fields import MISSING_NONPROP


@dataclasses.dataclass(frozen=True)
class _SubcommandConfiguration:
    name: str
    description: Optional[str]
    default: Any

    def __hash__(self) -> int:
        return object.__hash__(self)


def subcommand(
    name: str,
    *,
    description: Optional[str] = None,
    default: Any = MISSING_NONPROP,
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
    each subcommand the (a) name and (b) defaults.

    ```python
    dcargs.cli(
        Union[
            Annotated[
                NestedTypeA, subcommand("a", default=NestedTypeA(...))
            ],
            Annotated[
                NestedTypeA, subcommand("b", default=NestedTypeA(...))
            ],
        ]
    )
    ```
    """
    return _SubcommandConfiguration(name, description, default)
