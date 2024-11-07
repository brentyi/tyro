"""Counters

Repeatable 'counter' arguments can be specified via :data:`tyro.conf.UseCounterAction`.

Usage:

    python ./12_counters.py --help
    python ./12_counters.py --verbosity
    python ./12_counters.py --verbosity --verbosity
    python ./12_counters.py -vvv
"""

from typing_extensions import Annotated

import tyro
from tyro.conf import UseCounterAction


def main(
    verbosity: UseCounterAction[int],
    aliased_verbosity: Annotated[UseCounterAction[int], tyro.conf.arg(aliases=["-v"])],
) -> None:
    """Example showing how to use counter actions.

    Args:
        verbosity: Verbosity level.
        aliased_verbosity: Same as above, but can also be specified with -v, -vv, -vvv, etc.
    """
    print("Verbosity level:", verbosity)
    print("Verbosity level (aliased):", aliased_verbosity)


if __name__ == "__main__":
    tyro.cli(main)
