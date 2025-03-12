"""ML Collections + Field References

``ml_collections`` supports references for sharing values across multiple fields.

Usage:
    python ./04_ml_collections_refs.py --help
    python ./04_ml_collections_refs.py --config.layer-dims 32 32 32
    python ./04_ml_collections_refs.py --config.network.policy-layer-dims 64 64
"""

from pprint import pprint

import tyro
from ml_collections import ConfigDict, FieldReference  # type: ignore


def get_config() -> ConfigDict:
    config = ConfigDict()

    # Placeholder.
    layer_dim_ref = FieldReference((128,) * 3)
    config.layer_dims = layer_dim_ref

    # Wandb config.
    config.wandb = ConfigDict()
    config.wandb.mode = "online"  # online, offline, disabled.
    config.wandb.project = "robot-sandbox"

    # Network config.
    config.network = ConfigDict()
    config.network.policy_layer_dims = layer_dim_ref
    config.network.value_layer_dims = layer_dim_ref
    config.network.policy_obs_key = "state"
    config.network.value_obs_key = "state"

    return config


def train(config: ConfigDict = get_config()) -> None:
    """Train a model."""
    pprint(config.to_dict())  # type: ignore


if __name__ == "__main__":
    tyro.cli(train)
