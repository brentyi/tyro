from __future__ import annotations

from typing import Any, Callable, Dict, Sequence, TypeVar, Union, overload

from typing_extensions import Annotated

from tyro.conf._markers import Marker, Suppress
from tyro.constructors import ConstructorRegistry

from .._cli import cli
from ..conf import subcommand

T = TypeVar("T")


@overload
def subcommand_cli_from_dict(
    subcommands: Dict[str, Callable[..., T]],
    *,
    prog: str | None = None,
    description: str | None = None,
    args: Sequence[str] | None = None,
    use_underscores: bool = False,
    console_outputs: bool = True,
    config: Sequence[Marker] | None = None,
    sort_subcommands: bool = False,
    registry: ConstructorRegistry | None = None,
) -> T: ...


# TODO: hack. We prefer the above signature, which Pyright understands, but as of 1.6.1
# mypy doesn't reason about the generics properly.
@overload
def subcommand_cli_from_dict(
    subcommands: Dict[str, Callable[..., Any]],
    *,
    prog: str | None = None,
    description: str | None = None,
    args: Sequence[str] | None = None,
    use_underscores: bool = False,
    console_outputs: bool = True,
    config: Sequence[Marker] | None = None,
    sort_subcommands: bool = False,
    registry: ConstructorRegistry | None = None,
) -> Any: ...


def subcommand_cli_from_dict(
    subcommands: Dict[str, Callable[..., Any]],
    *,
    prog: str | None = None,
    description: str | None = None,
    args: Sequence[str] | None = None,
    use_underscores: bool = False,
    console_outputs: bool = True,
    config: Sequence[Marker] | None = None,
    sort_subcommands: bool = False,
    registry: ConstructorRegistry | None = None,
) -> Any:
    """Generate a subcommand CLI from a dictionary of functions.

    For an input like:

    .. code-block:: python

        tyro.extras.subcommand_cli_from_dict(
            {
                "checkout": checkout,
                "commit": commit,
            }
        )

    This is internally accomplished by generating and calling:

    .. code-block:: python

        from typing import Annotated, Any, Union
        import tyro

        tyro.cli(
            Union[
                Annotated[
                    Any,
                    tyro.conf.subcommand(name="checkout", constructor=checkout),
                ],
                Annotated[
                    Any,
                    tyro.conf.subcommand(name="commit", constructor=commit),
                ],
            ]
        )

    Args:
        subcommands: Dictionary that maps the subcommand name to function to call.
        prog: The name of the program printed in helptext. Mirrors argument from
            :py:class:`argparse.ArgumentParser`.
        description: Description text for the parser, displayed when the --help flag is
            passed in. If not specified, `f`'s docstring is used. Mirrors argument from
            :py:class:`argparse.ArgumentParser`.
        args: If set, parse arguments from a sequence of strings instead of the
            commandline. Mirrors argument from :py:meth:`argparse.ArgumentParser.parse_args()`.
        use_underscores: If True, use underscores as a word delimeter instead of hyphens.
            This primarily impacts helptext; underscores and hyphens are treated equivalently
            when parsing happens. We default helptext to hyphens to follow the GNU style guide.
            https://www.gnu.org/software/libc/manual/html_node/Argument-Syntax.html
        console_outputs: If set to ``False``, parsing errors and help messages will be
            supressed. This can be useful for distributed settings, where :func:`tyro.cli()`
            is called from multiple workers but we only want console outputs from the
            main one.
        config: Sequence of config marker objects, from :mod:`tyro.conf`.
        registry: A :class:`tyro.constructors.ConstructorRegistry` instance containing custom
            constructor rules.
    """

    keys = list(subcommands.keys())
    if sort_subcommands:
        keys = sorted(keys)

    # We need to form a union type, which requires at least two elements.
    return cli(
        Union[  # type: ignore
            tuple(
                [
                    Annotated[
                        # The constructor function can return any object.
                        Any,
                        # We'll instantiate this object by invoking a subcommand with
                        # name k, via a constructor.
                        subcommand(name=k, constructor=subcommands[k]),
                    ]
                    for k in keys
                ]
                # Union types need at least two types. To support the case
                # where we only pass one subcommand in, we'll pad with `None`
                # but suppress it.
                + [Annotated[None, Suppress]]
            )
        ],
        prog=prog,
        description=description,
        args=args,
        use_underscores=use_underscores,
        console_outputs=console_outputs,
        config=config,
        registry=registry,
    )
