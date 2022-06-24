"""An example of how we can create hierarchical configuration interfaces by nesting
dataclasses."""

import dataclasses
import enum
import pathlib

import dcargs


class OptimizerType(enum.Enum):
    ADAM = enum.auto()
    SGD = enum.auto()


@dataclasses.dataclass(frozen=True)
class OptimizerConfig:
    # Gradient-based optimizer to use.
    algorithm: OptimizerType = OptimizerType.ADAM

    # Learning rate to use.
    learning_rate: float = 3e-4

    # Coefficient for L2 regularization.
    weight_decay: float = 1e-2


@dataclasses.dataclass(frozen=True)
class ExperimentConfig:
    # Various configurable options for our optimizer.
    optimizer: OptimizerConfig

    # Batch size.
    batch_size: int = 32

    # Total number of training steps.
    train_steps: int = 100_000

    # Random seed. This is helpful for making sure that our experiments are all
    # reproducible!
    seed: int = 0


def train(
    out_dir: pathlib.Path,
    /,
    config: ExperimentConfig,
    restore_checkpoint: bool = False,
    checkpoint_interval: int = 1000,
) -> None:
    """Train a model.

    Args:
        out_dir: Where to save logs and checkpoints.
        config: Experiment configuration.
        restore_checkpoint: Set to restore an existing checkpoint.
        checkpoint_interval: Training steps between each checkpoint save.
    """
    print(out_dir)
    print("---")
    print(dcargs.to_yaml(config))
    print("---")
    print(restore_checkpoint)
    print(checkpoint_interval)


if __name__ == "__main__":
    dcargs.cli(train)
