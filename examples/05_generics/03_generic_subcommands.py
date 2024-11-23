# mypy: ignore-errors
#
# Passing a Union type directly to tyro.cli() doesn't type-check correctly in
# mypy. This will be fixed by `typing.TypeForm`: https://peps.python.org/pep-0747/
"""Generic Subcommands

Just like standard classes, generic classes within unions can be selected
between using subcommands.

Usage:

    python ./03_generic_subcommands.py --help
    python ./03_generic_subcommands.py experiment-adam --help
    python ./03_generic_subcommands.py experiment-sgd --help
    python ./03_generic_subcommands.py experiment-adam --path /tmp --opt.lr 1e-3
"""

import dataclasses
from pathlib import Path

import tyro


@dataclasses.dataclass
class Sgd:
    lr: float = 1e-4


@dataclasses.dataclass
class Adam:
    lr: float = 3e-4
    betas: tuple[float, float] = (0.9, 0.999)


@dataclasses.dataclass
class Experiment[OptimizerT: (Adam, Sgd)]:
    path: Path
    opt: OptimizerT


if __name__ == "__main__":
    args = tyro.cli(Experiment[Adam] | Experiment[Sgd])
    print(args)
