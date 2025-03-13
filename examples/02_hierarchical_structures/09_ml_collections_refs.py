"""ML Collections + Field References

``ml_collections`` supports references for sharing values across multiple fields.

Usage:
    python ./09_ml_collections_refs.py --help
    python ./09_ml_collections_refs.py --config.hidden-dim 32
    python ./09_ml_collections_refs.py --config.network.policy-hidden-dim 64
"""

from pprint import pprint

from ml_collections import ConfigDict, FieldReference  # type: ignore

import tyro


def get_config() -> ConfigDict:
    config = ConfigDict()

    # Placeholder.
    hidden_dim_ref = FieldReference(128)
    config.hidden_dim = hidden_dim_ref

    # Wandb config.
    config.wandb = ConfigDict()
    config.wandb.mode = "online"  # online, offline, disabled.
    config.wandb.project = "robot-sandbox"

    # Network config.
    # Updating `policy_hidden_dim` will update `value_hidden_dim`, but
    # updating `value_hidden_dim` will not update `policy_hidden_dim`.
    config.network = ConfigDict()
    config.network.policy_hidden_dim = hidden_dim_ref
    config.network.value_hidden_dim = hidden_dim_ref * 2
    config.network.policy_obs_key = "state"
    config.network.value_obs_key = "state"

    return config


def train(config: ConfigDict = get_config()) -> None:
    """Train a model."""
    pprint(config.to_dict())  # type: ignore


if __name__ == "__main__":
    tyro.cli(train)
