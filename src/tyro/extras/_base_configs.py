from typing import Mapping, Optional, Sequence, Tuple, TypeVar, Union

from typing_extensions import Annotated

from .._typing import TypeForm

T = TypeVar("T")


def overridable_config_cli(
    configs: Mapping[str, Tuple[str, T]],
    *,
    args: Optional[Sequence[str]] = None,
) -> T:
    """Helper function for creating a CLI interface that allows us to choose
    between default config objects (typically dataclasses) and override values
    within it. Turns off subcommand creation for any union types within the
    config object.

    This is a lightweight wrapper over :func:`tyro.cli()`, with some default
    arguments populated. Also see
    :func:`tyro.extras.subcommand_type_from_defaults()`.


    Example usage:

    .. code-block:: python

        import dataclasses

        import tyro


        @dataclasses.dataclass
        class Config:
            a: int
            b: str


        default_configs = {
            "small": (
                "Small config",
                Config(1, "small"),
            ),
            "big": (
                "Big config",
                Config(100, "big"),
            ),
        }
        config = tyro.extras.overridable_config_cli(default_configs)
        print(config)

    Args:
        configs: A dictionary of config names mapped to a tuple of
            (description, config object).
        args: Optional arguments to pass to the CLI.
    """
    import tyro

    return tyro.cli(
        tyro.extras.subcommand_type_from_defaults(
            defaults={k: v[1] for k, v in configs.items()},
            descriptions={k: v[0] for k, v in configs.items()},
        ),
        # Don't create subcommands for union types within the config object.
        config=(tyro.conf.AvoidSubcommands,),
        args=args,
    )


def subcommand_type_from_defaults(
    defaults: Mapping[str, T],
    descriptions: Mapping[str, str] = {},
    *,
    prefix_names: bool = True,
) -> TypeForm[T]:
    """Construct a Union type for defining subcommands that choose between defaults.

    For example, when ``defaults`` is set to:

    .. code-block:: python

        {
            "small": Config(...),
            "big": Config(...),
        }

    We return:

    .. code-block:: python

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

    Direct use of :py:data:`typing.Union` and :func:`tyro.conf.subcommand()` should generally be
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
    import tyro

    # We need to form a union type, which requires at least two elements.
    assert len(defaults) >= 2, "At least two subcommands are required."
    return Union.__getitem__(  # type: ignore
        tuple(
            Annotated[  # type: ignore
                (
                    type(v),
                    tyro.conf.subcommand(
                        k,
                        default=v,
                        description=descriptions.get(k, ""),
                        prefix_name=prefix_names,
                    ),
                )
            ]
            for k, v in defaults.items()
        )
    )
