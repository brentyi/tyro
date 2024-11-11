"""Nested Dataclasses

Structures (typically :py:func:`dataclasses.dataclass`) can be nested to build hierarchical configuration
objects. This helps with modularity and grouping in larger projects.

Usage:

    python ./01_nesting.py --help
    python ./01_nesting.py --opt.learning-rate 1e-3
    python ./01_nesting.py --seed 4
"""

import dataclasses

import tyro


@dataclasses.dataclass
class OptimizerConfig:
    learning_rate: float = 3e-4
    weight_decay: float = 1e-2


@dataclasses.dataclass
class Config:
    # Optimizer options.
    opt: OptimizerConfig

    # Random seed.
    seed: int = 0


if __name__ == "__main__":
    config = tyro.cli(Config)
    print(dataclasses.asdict(config))
