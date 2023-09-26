"""Sequenced Subcommands

Multiple unions over nested types are populated using a series of subcommands.

Usage:
`python ./03_multiple_subcommands.py --help`
`python ./03_multiple_subcommands.py dataset:mnist --help`
`python ./03_multiple_subcommands.py dataset:mnist optimizer:adam --help`
`python ./03_multiple_subcommands.py dataset:mnist optimizer:adam --optimizer.learning-rate 3e-4 --dataset.binary`
"""
from __future__ import annotations

import dataclasses
from typing import Literal, Tuple, Union

import tyro

# Possible dataset configurations.


@dataclasses.dataclass
class Mnist:
    binary: bool = False
    """Set to load binary version of MNIST dataset."""


@dataclasses.dataclass
class ImageNet:
    subset: Literal[50, 100, 1000]
    """Choose between ImageNet-50, ImageNet-100, ImageNet-1000, etc."""


# Possible optimizer configurations.


@dataclasses.dataclass
class Adam:
    learning_rate: float = 1e-3
    betas: Tuple[float, float] = (0.9, 0.999)


@dataclasses.dataclass
class Sgd:
    learning_rate: float = 3e-4


# Train script.


@tyro.conf.configure(tyro.conf.ConsolidateSubcommandArgs)
def train(
    dataset: Union[Mnist, ImageNet] = Mnist(),
    optimizer: Union[Adam, Sgd] = Adam(),
) -> None:
    """Example training script.

    Args:
        dataset: Dataset to train on.
        optimizer: Optimizer to train with.

    Returns:
        None:
    """
    print(dataset)
    print(optimizer)


if __name__ == "__main__":
    tyro.cli(train)
