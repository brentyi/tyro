from typing import Any, Callable, Dict, Optional, Sequence, TypeVar, Union, overload

from typing_extensions import Annotated

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
) -> T:
    ...


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
) -> Any:
    ...


def subcommand_cli_from_dict(
    subcommands: Dict[str, Callable[..., Any]],
    *,
    prog: Optional[str] = None,
    description: Optional[str] = None,
    args: Optional[Sequence[str]] = None,
    use_underscores: bool = False,
) -> Any:
    """Generate a subcommand CLI from a dictionary of functions.

    For an input like:

    ```python
    tyro.extras.subcommand_cli_from_dict(
        {
            "checkout": checkout,
            "commit": commit,
        }
    )
    ```

    This is internally accomplished by generating and calling:

    ```python
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
    ```

    Args:
        subcommands: Dictionary that maps the subcommand name to function to call.
        prog: The name of the program printed in helptext. Mirrors argument from
            `argparse.ArgumentParser()`.
        description: Description text for the parser, displayed when the --help flag is
            passed in. If not specified, `f`'s docstring is used. Mirrors argument from
            `argparse.ArgumentParser()`.
        args: If set, parse arguments from a sequence of strings instead of the
            commandline. Mirrors argument from `argparse.ArgumentParser.parse_args()`.
        use_underscores: If True, use underscores as a word delimeter instead of hyphens.
            This primarily impacts helptext; underscores and hyphens are treated equivalently
            when parsing happens. We default helptext to hyphens to follow the GNU style guide.
            https://www.gnu.org/software/libc/manual/html_node/Argument-Syntax.html
    """
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
    )
