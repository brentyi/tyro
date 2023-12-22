from typing import Mapping, TypeVar, Union

from typing_extensions import Annotated

from .._typing import TypeForm
from ..conf import subcommand

T = TypeVar("T")


def subcommand_type_from_defaults(
    defaults: Mapping[str, T],
    descriptions: Mapping[str, str] = {},
    *,
    prefix_names: bool = True,
) -> TypeForm[T]:
    """Construct a Union type for defining subcommands that choose between defaults.

    For example, when `defaults` is set to:

    ```python
    {
        "small": Config(...),
        "big": Config(...),
    }
    ```

    We return:

    ```python
    Union[
        Annotated[
            Config,
            tyro.conf.subcommand("small", default=Config(...))
        ],
        Annotated[
            Config,
            tyro.conf.subcommand("big", default=Config(...))
        ]
    ]
    ```

    Direct use of `typing.Union` and :func:`tyro.conf.subcommand()` should generally be
    preferred, but this function can be helpful for succinctness.

    .. warning::
        The type returned by this function can be safely used as an input to
        :func:`tyro.cli()`, but for static analysis when used for annotations we
        recommend applying a `TYPE_CHECKING` guard:

        .. code-block:: python

            from typing import TYPE_CHECKING

            if TYPE_CHECKING:
                # Static type seen by language servers, type checkers, etc.
                SelectableConfig = Config
            else:
                # Runtime type used by tyro.
                SelectableConfig = subcommand_type_from_defaults(...)

    Args:
        defaults: A dictionary of default subcommand instances.
        descriptions: A dictionary conttaining descriptions for helptext.
        prefix_names: Whether to prefix subcommand names.

    Returns:
        A subcommand type, which can be passed to :func:`tyro.cli`.
    """
    return Union.__getitem__(  # type: ignore
        tuple(
            Annotated.__class_getitem__(  # type: ignore
                (
                    type(v),
                    subcommand(
                        k,
                        default=v,
                        description=descriptions.get(k, ""),
                        prefix_name=prefix_names,
                    ),
                )
            )
            for k, v in defaults.items()
        )
    )
