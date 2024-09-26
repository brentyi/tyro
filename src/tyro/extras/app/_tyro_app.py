from __future__ import annotations

from typing import Any, Callable, Dict, TypeVar

import tyro

CallableT = TypeVar("CallableT", bound=Callable)


_subcommands: Dict[str, Callable] | None = None


def command(name: str | None = None) -> Callable[[CallableT], CallableT]:
    """A decorator to register a function as a subcommand.

    This method is inspired by Click's @cli.command() decorator.
    It adds the decorated function to the list of subcommands.

    Args:
        name: The name of the subcommand. If None, the name of the function is used.
    """

    def inner(func: CallableT) -> CallableT:
        global _subcommands
        if _subcommands is None:
            _subcommands = {}

        nonlocal name
        if name is None:
            name = func.__name__

        _subcommands[name] = func
        return func

    return inner


def cli() -> Any:
    """Run the command-line interface.

    This method creates a CLI using tyro, with all subcommands registered using
    :func:`command()`.
    """
    assert _subcommands is not None
    if len(_subcommands) == 1:
        return tyro.cli(next(iter(_subcommands.values())))
    else:
        return tyro.extras.subcommand_cli_from_dict(_subcommands)
