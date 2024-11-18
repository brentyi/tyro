"""Nesting in Containers

Structures can be nested inside of standard containers.

.. warning::

    When placing structures inside of containers like lists or tuples, the
    length of the container must be inferrable from the annotation or default
    value.


Usage:

    python ./03_nesting_containers.py --help
"""

import dataclasses

import tyro


@dataclasses.dataclass
class RGB:
    r: int
    g: int
    b: int


@dataclasses.dataclass
class Args:
    color_tuple: tuple[RGB, RGB]
    color_dict: dict[str, RGB] = dataclasses.field(
        # We can't use mutable values as defaults directly.
        default_factory=lambda: {
            "red": RGB(255, 0, 0),
            "green": RGB(0, 255, 0),
            "blue": RGB(0, 0, 255),
        }
    )


if __name__ == "__main__":
    args = tyro.cli(Args)
    print(args)
