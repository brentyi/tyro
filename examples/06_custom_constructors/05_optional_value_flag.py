"""Flag with an optional value

A primitive constructor with ``nargs="*"`` can define a flag that is used either
alone or with a single value, similar to ``nargs="?"`` in argparse. Here,
``--cache`` alone turns caching on, and ``--cache DIR`` also sets the directory.

The flag consumes values up to the next flag, leaving any that a required
positional argument still needs: ``--cache data.csv`` caches in the default
directory.

Usage:

    python ./05_optional_value_flag.py --help
    python ./05_optional_value_flag.py data.csv
    python ./05_optional_value_flag.py data.csv --cache
    python ./05_optional_value_flag.py data.csv --cache /tmp/cache
    python ./05_optional_value_flag.py --cache data.csv
"""

from pathlib import Path
from typing import Union

from typing_extensions import Annotated

import tyro


def _cache_from_args(args: list) -> Union[Path, bool]:
    if len(args) > 1:
        raise ValueError("--cache takes at most one directory")
    return Path(args[0]) if args else True


# False when the flag is omitted, True for `--cache`, a path for `--cache DIR`.
Cache = Annotated[
    Union[Path, bool],
    tyro.constructors.PrimitiveConstructorSpec(
        # Zero or more values; `instance_from_str` rejects more than one.
        nargs="*",
        metavar="[DIR]",
        instance_from_str=_cache_from_args,
        is_instance=lambda instance: isinstance(instance, (Path, bool)),
        str_from_instance=lambda instance: (
            [str(instance)] if isinstance(instance, Path) else []
        ),
    ),
    # Without a hint, the helptext would show an empty default.
    tyro.conf.arg(help_behavior_hint="(default: off)"),
]


def main(data: tyro.conf.Positional[Path], cache: Cache = False) -> None:
    """Process a data file.

    Args:
        data: Input file.
        cache: Cache results, optionally in DIR.
    """
    print(f"{data=} {cache=}")


if __name__ == "__main__":
    tyro.cli(main)
