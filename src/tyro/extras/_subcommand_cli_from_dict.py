from typing import Any, Callable, Dict, Optional, Sequence, TypeVar, Union, overload

from typing_extensions import Annotated

from tyro.conf._markers import Marker

from .._cli import cli
from ..conf import subcommand

T = TypeVar("T")


@overload
def subcommand_cli_from_dict(
    subcommands: Dict[str, Callable[..., T]],
    *,
    prog: Optional[str] = None,
    description: Optional[str] = None,
    args: Optional[Sequence[str]] = None,
    use_underscores: bool = False,
    console_outputs: bool = True,
    config: Optional[Sequence[Marker]] = None,
) -> T: ...


# TODO: hack. We prefer the above signature, which Pyright understands, but as of 1.6.1
# mypy doesn't reason about the generics properly.
@overload
def subcommand_cli_from_dict(
    subcommands: Dict[str, Callable[..., Any]],
    *,
    prog: Optional[str] = None,
    description: Optional[str] = None,
    args: Optional[Sequence[str]] = None,
    use_underscores: bool = False,
    console_outputs: bool = True,
    config: Optional[Sequence[Marker]] = None,
) -> Any: ...


def subcommand_cli_from_dict(
    subcommands: Dict[str, Callable[..., Any]],
    *,
    prog: Optional[str] = None,
    description: Optional[str] = None,
    args: Optional[Sequence[str]] = None,
    use_underscores: bool = False,
    console_outputs: bool = True,
    config: Optional[Sequence[Marker]] = None,
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
    """
    # We need to form a union type, which requires at least two elements.
    assert len(subcommands) >= 2, "At least two subcommands are required."
    return cli(
        Union.__getitem__(  # type: ignore
            tuple(
                [
                    Annotated[
                        # The constructor function can return any object.
                        Any,
                        # We'll instantiate this object by invoking a subcommand with
                        # name k, via a constructor.
                        subcommand(name=k, constructor=v),
                    ]
                    for k, v in subcommands.items()
                ]
            )
        ),
        prog=prog,
        description=description,
        args=args,
        use_underscores=use_underscores,
        console_outputs=console_outputs,
        config=config,
    )
