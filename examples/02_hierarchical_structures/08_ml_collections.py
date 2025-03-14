"""ML Collections

:func:`tyro.cli` understands and can populate config objects implemented using
`ml_collections <https://github.com/google/ml_collections/>`_, which is an
excellent library from folks at Google.

``ml_collections`` structures aren't statically typed, so we infer field types
based on value.

Usage:

    python ./08_ml_collections.py --help
    python ./08_ml_collections.py --config.network.policy-layer-dims 64 64 64
"""

from pprint import pprint

from ml_collections import ConfigDict, FrozenConfigDict  # type: ignore

import tyro


def get_config() -> FrozenConfigDict:
    config = ConfigDict()

    # Wandb config.
    config.wandb = ConfigDict()
    config.wandb.mode = "online"  # online, offline, disabled.
    config.wandb.project = "robot-sandbox"

    # Network config.
    config.network = ConfigDict()
    config.network.policy_layer_dims = (128,) * 3
    config.network.value_layer_dims = (256,) * 5
    config.network.policy_obs_key = "state"
    config.network.value_obs_key = "state"

    return FrozenConfigDict(config)


def train(config: FrozenConfigDict = get_config()) -> None:
    """Train a model."""
    pprint(config.to_dict())  # type: ignore


if __name__ == "__main__":
    tyro.cli(train)
