"""Subcommands from Functions

:func:`tyro.extras.subcommand_cli_from_dict()` provides a shorthand that generates a
subcommand CLI from a dictionary.

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

Usage:
`python ./05_subcommands_func.py --help`
`python ./05_subcommands_func.py commit --help`
`python ./05_subcommands_func.py commit --message hello --all`
`python ./05_subcommands_func.py checkout --help`
`python ./05_subcommands_func.py checkout --branch main`
"""

import tyro


def checkout(branch: str) -> None:
    """Check out a branch."""
    print(f"{branch=}")


def commit(message: str, all: bool = False) -> None:
    """Make a commit."""
    print(f"{message=} {all=}")


if __name__ == "__main__":
    tyro.extras.subcommand_cli_from_dict(
        {
            "checkout": checkout,
            "commit": commit,
        }
    )
