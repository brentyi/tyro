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

    .. warning::

        Use of this helper is discouraged. It will likely be deprecated.

        Using the the returned type is understood as an annotation by ``pyright`` and
        ``pylance`` (with ``from __future__ import annotations``), but it relies on
        behavior that isn't defined by the Python language specifications.

        At the cost of verbosity, using :func:`tyro.conf.subcommand()` directly is
        better supported by tools like ``mypy``.

        Alternatively, we can work around this limitation with an ``if TYPE_CHECKING``
        guard:

        .. code-block:: python

            from typing import TYPE_CHECKING

            if TYPE_CHECKING:
                # Static type seen by mypy, language servers, etc.
                SelectableConfig = Config
            else:
                # Runtime type used by tyro.
                SelectableConfig = subcommand_type_from_defaults(...)


    This can most commonly be used to create a "base configuration" pattern:
        https://brentyi.github.io/tyro/examples/10_base_configs/

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

    The resulting type can be used directly in tyro.cli:

    ```python
    config = tyro.cli(subcommand_type_from_defaults(default_from_name))
    reveal_type(config)  # Should be correct!
    ```

    Or to generate annotations for classes and functions:

    ```python
    SelectableConfig = subcommand_type_from_defaults(default_from_name)

    def train(
        config: SelectableConfig,
        checkpoint_path: Optional[pathlib.Path] = None,
    ) -> None:
        ...

    tyro.cli(train)
    ```
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
