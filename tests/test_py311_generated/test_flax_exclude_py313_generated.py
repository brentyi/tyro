"""Tests initializing flax modules directly via tyro."""

from typing import cast

import jax
import pytest
from flax import linen as nn
from helptext_utils import get_helptext_with_checks
from jax import numpy as jnp

import tyro


class Classifier(nn.Module):
    layers: int
    units: int
    output_dim: int

    @nn.compact
    def __call__(self, x: jnp.ndarray) -> jnp.ndarray:  # type: ignore
        for i in range(self.layers - 1):
            x = nn.Dense(
                self.units,
                kernel_init=nn.initializers.kaiming_normal(),
            )(x)
            x = nn.relu(x)

        x = nn.Dense(
            self.output_dim,
            kernel_init=nn.initializers.xavier_normal(),
        )(x)
        x = nn.sigmoid(x)
        return x


def test_ok():
    network = tyro.cli(
        Classifier,
        args=[
            "--layers",
            "3",
            "--units",
            "8",
            "--output-dim",
            "3",
        ],
    )

    x = jnp.zeros((10, 4))
    params = network.init(jax.random.PRNGKey(0), x)
    assert cast(jax.Array, network.apply(params, x)).shape == (10, 3)

    helptext = get_helptext_with_checks(Classifier)
    assert "parent" not in helptext
    assert "name" not in helptext


def test_missing():
    with pytest.raises(SystemExit):
        tyro.cli(
            Classifier,
            args=[
                "--layers",
                "3",
                "--units",
                "8",
            ],
        )
