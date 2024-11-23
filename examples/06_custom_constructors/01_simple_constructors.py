"""Simple Constructors

For simple custom constructors, we can pass a constructor function into
:func:`tyro.conf.arg` or :func:`tyro.conf.subcommand`. Arguments will be
generated by parsing the signature of the constructor function.

In this example, we define custom behavior for instantiating a NumPy array.

Usage:

    python ./01_simple_constructors.py --help
    python ./01_simple_constructors.py --array.values 1 2 3
    python ./01_simple_constructors.py --array.values 1 2 3 4 5 --array.dtype float32
"""

from typing import Literal

import numpy as np
from typing_extensions import Annotated

import tyro


def construct_array(
    values: tuple[float, ...], dtype: Literal["float32", "float64"] = "float64"
) -> np.ndarray:
    """A custom constructor for 1D NumPy arrays."""
    return np.array(
        values,
        dtype={"float32": np.float32, "float64": np.float64}[dtype],
    )


def main(
    # We can specify a custom constructor for an argument in `tyro.conf.arg()`.
    array: Annotated[np.ndarray, tyro.conf.arg(constructor=construct_array)],
) -> None:
    print(f"{array=}")


if __name__ == "__main__":
    tyro.cli(main)
