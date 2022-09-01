from typing import Mapping, Tuple, Type, TypeVar, Union

from typing_extensions import Annotated

from ..metadata import subcommand

T = TypeVar("T")


def union_type_from_mapping(
    base_mapping: Mapping[Union[str, Tuple[str, str]], T]
) -> Type[T]:
    """Returns a Union type for defining subcommands that choose between nested types.

    For example, when `base_mapping` is set to:

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
            dcargs.metadata.subcommand("small", default=Config(...))
        ],
        Annotated[
            Config,
            dcargs.metadata.subcommand("big", default=Config(...))
        ]
    ]
    ```

    This can be used directly in dcargs.cli:

    ```python
    config = dcargs.cli(union_from_base_mapping(base_mapping))
    reveal_type(config)  # Should be correct!
    ```

    Or to generate annotations for functions:

    ```python
    SelectableConfig = union_from_base_mapping(base_mapping)

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
        SelectableConfig = union_from_base_mapping(base_mapping)
    ```
    """
    return Union.__getitem__(  # type: ignore
        tuple(
            Annotated.__class_getitem__(  # type: ignore
                (
                    type(v),
                    subcommand(k, default=v)
                    if isinstance(k, str)
                    else subcommand(k[0], default=v, description=k[1]),
                )
            )
            for k, v in base_mapping.items()
        )
    )
