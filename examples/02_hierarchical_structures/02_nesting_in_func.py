"""Structures as Function Arguments

Structures can be used as input to functions.

Usage:

    python ./02_nesting_in_func.py --help
    python ./02_nesting_in_func.py --out-dir /tmp/test1
    python ./02_nesting_in_func.py --out-dir /tmp/test2 --config.seed 4
"""

import dataclasses
import pathlib

import tyro


@dataclasses.dataclass
class OptimizerConfig:
    learning_rate: float = 3e-4
    weight_decay: float = 1e-2


@dataclasses.dataclass
class Config:
    # Optimizer options.
    optimizer: OptimizerConfig

    # Random seed.
    seed: int = 0


def train(
    out_dir: pathlib.Path,
    config: Config,
) -> None:
    """Train a model.

    Args:
        out_dir: Where to save logs and checkpoints.
        config: Experiment configuration.
    """
    print(f"Saving to: {out_dir}")
    print(f"Config: {config}")


if __name__ == "__main__":
    tyro.cli(train)
