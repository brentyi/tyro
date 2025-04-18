from __future__ import annotations

from typing import Any, Mapping, Sequence, Tuple, TypeVar, Union

from typing_extensions import Annotated

from tyro.conf._markers import Suppress
from tyro.constructors import ConstructorRegistry

from .._typing import TypeForm

T = TypeVar("T")


def overridable_config_cli(
    configs: Mapping[str, Tuple[str, T]],
    *,
    prog: str | None = None,
    description: str | None = None,
    args: Sequence[str] | None = None,
    use_underscores: bool = False,
    console_outputs: bool = True,
    config: Sequence[Any] | None = None,
    sort_subcommands: bool = False,
    registry: ConstructorRegistry | None = None,
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
        prog: The name of the program printed in helptext. Mirrors argument from
            `argparse.ArgumentParser()`.
        description: Description text for the parser, displayed when the --help flag is
            passed in. If not specified, the class docstring is used. Mirrors argument from
            `argparse.ArgumentParser()`.
        args: If set, parse arguments from a sequence of strings instead of the
            commandline. Mirrors argument from `argparse.ArgumentParser.parse_args()`.
        use_underscores: If True, use underscores as a word delimiter instead of hyphens.
            This primarily impacts helptext; underscores and hyphens are treated equivalently
            when parsing happens. We default helptext to hyphens to follow the GNU style guide.
            https://www.gnu.org/software/libc/manual/html_node/Argument-Syntax.html
        console_outputs: If set to `False`, parsing errors and help messages will be
            suppressed.
        config: Sequence of config marker objects, from `tyro.conf`. We include
            :class:`tyro.conf.AvoidSubcommands` by default.
        sort_subcommands: If True, sort the subcommands alphabetically by name.
        registry: A :class:`tyro.constructors.ConstructorRegistry` instance containing custom
            constructor rules.
    """
    import tyro

    keys = list(configs.keys())
    return tyro.cli(
        tyro.extras.subcommand_type_from_defaults(
            defaults={k: configs[k][1] for k in keys},
            descriptions={k: configs[k][0] for k in keys},
            sort_subcommands=sort_subcommands,
        ),
        prog=prog,
        description=description,
        args=args,
        use_underscores=use_underscores,
        console_outputs=console_outputs,
        # Don't create subcommands for union types within the config object.
        config=(tyro.conf.AvoidSubcommands,)
        + (tuple() if config is None else tuple(config)),
        registry=registry,
    )


def subcommand_type_from_defaults(
    defaults: Mapping[str, T],
    descriptions: Mapping[str, str] = {},
    *,
    prefix_names: bool = True,
    sort_subcommands: bool = False,
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
        sort_subcommands: If True, sort the subcommands alphabetically by name.

    Returns:
        A subcommand type, which can be passed to :func:`tyro.cli`.
    """
    import tyro

    keys = list(defaults.keys())
    if sort_subcommands:
        keys = sorted(keys)
    return Union[  # type: ignore
        tuple(
            Annotated[  # type: ignore
                (
                    type(defaults[k]),
                    tyro.conf.subcommand(
                        k,
                        default=defaults[k],
                        description=descriptions.get(k, ""),
                        prefix_name=prefix_names,
                    ),
                )
            ]
            for k in keys
        )
        # Union types need at least two types. To support the case
        # where we only pass one subcommand in, we'll pad with `None`
        # but suppress it.
        + (Annotated[None, Suppress],)
    ]
