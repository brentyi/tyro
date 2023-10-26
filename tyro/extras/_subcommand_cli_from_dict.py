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
    """Generate a subcommand CLI from a dictionary that maps subcommand name to the
    corresponding function to call (or object to instantiate)."""
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
