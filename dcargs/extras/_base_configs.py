from typing import Mapping, Type, TypeVar, Union

from typing_extensions import Annotated

from ..conf import subcommand

T = TypeVar("T")


def subcommand_type_from_defaults(
    defaults: Mapping[str, T],
    descriptions: Mapping[str, str] = {},
    *,
    prefix_names: bool = True,
) -> Type[T]:
    """Construct a Union type for defining subcommands that choose between defaults.

    This can most commonly be used to create a "base configuration" pattern:
        https://brentyi.github.io/dcargs/examples/10_base_configs/

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
            dcargs.conf.subcommand("small", default=Config(...))
        ],
        Annotated[
            Config,
            dcargs.conf.subcommand("big", default=Config(...))
        ]
    ]
    ```

    The resulting type can be used directly in dcargs.cli:

    ```python
    config = dcargs.cli(subcommand_type_from_defaults(default_from_name))
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

    dcargs.cli(train)
    ```

    Note that Pyright understands the latter case, but mypy does not. If mypy support is
    necessary we can work around this with an `if TYPE_CHECKING` guard:

    ```python
    if TYPE_CHECKING:
        SelectableConfig = ExperimentConfig
    else:
        SelectableConfig = subcommand_type_from_defaults(base_mapping)
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
