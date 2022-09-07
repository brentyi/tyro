from typing import Mapping, Type, TypeVar, Union

from typing_extensions import Annotated

from ..conf import subcommand

T = TypeVar("T")


def subcommand_union_from_mapping(
    default_from_name: Mapping[str, T], descriptions: Mapping[str, str] = {}
) -> Type[T]:
    """Returns a Union type for defining subcommands that choose between nested types.

    For example, when `default` is set to:

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

    This can be used directly in dcargs.cli:

    ```python
    config = dcargs.cli(subcommand_union_from_mapping(default_from_name))
    reveal_type(config)  # Should be correct!
    ```

    Or to generate annotations for classes and functions:

    ```python
    SelectableConfig = subcommand_union_from_mapping(default_from_name)

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
        SelectableConfig = subcommand_union_from_mapping(base_mapping)
    ```
    """
    return Union.__getitem__(  # type: ignore
        tuple(
            Annotated.__class_getitem__(  # type: ignore
                (type(v), subcommand(k, default=v, description=descriptions.get(k)))
            )
            for k, v in default_from_name.items()
        )
    )
