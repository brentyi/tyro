"""Verbosity flags

:class:`tyro.extras.Verbosity` provides standard ``-v``/``--verbose`` and
``-q``/``--quiet`` count flags that map to Python :mod:`logging` levels,
with the two flags being mutually exclusive.

By default, when ``Verbosity`` is a nested field, long flags carry the field
prefix (``--verbosity.verbose``). Annotating with
:data:`tyro.conf.OmitArgPrefixes` promotes them to the top level
(``--verbose``, ``--quiet``). Short aliases ``-v`` and ``-q`` always work
regardless of nesting.

Inspired by `clap-verbosity-flag <https://docs.rs/clap-verbosity-flag>`_ from
the Rust/clap ecosystem.

Usage:

    python ./16_verbosity.py --help
    python ./16_verbosity.py -v
    python ./16_verbosity.py -vv
    python ./16_verbosity.py -q
    python ./16_verbosity.py --verbose
    python ./16_verbosity.py --quiet --quiet
"""

import dataclasses
import logging
from pathlib import Path
from typing import Annotated

import tyro
from tyro.conf import OmitArgPrefixes
from tyro.extras import Verbosity

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Args:
    """Process files with configurable log verbosity."""

    path: Path = dataclasses.field(default_factory=Path.cwd)
    """Path to process."""

    # Log verbosity. OmitArgPrefixes promotes --verbosity.verbose/--verbosity.quiet
    # to --verbose/--quiet at the top level.
    verbosity: Annotated[Verbosity, OmitArgPrefixes] = dataclasses.field(
        default_factory=Verbosity
    )


if __name__ == "__main__":
    args = tyro.cli(Args)
    logging.basicConfig(level=args.verbosity.log_level())
    logger.info("path=%s", args.path)
