"""Custom Constructors

For additional flexibility, :func:`tyro.conf.arg()` accepts a
:code:`constructor` argument, which makes it easier to load complex objects.

.. warning::
    Custom constructors are permitted wherever :func:`tyro.conf.arg()` is. This
    annotation corresponds to a single argument, so we expect that it is placed
    placed at the root of the field corresponding to that argument. For
    example:

    .. code-block:: python

        # Great!
        x: Annotated[int, tyro.conf.arg(custom_constructor=...)]

    However, nesting :func:`tyro.conf.arg()` within other types is generally
    not supported. For example:

    .. code-block:: python

        # Not supported.
        x: tuple[Annotated[int, tyro.conf.arg(custom_constructor=...)], ...]

    This example can be rewritten with a custom constructor that directly
    returns a tuple of integers:

    .. code-block:: python

        # Workaround for above.
        x: Annotated[tuple[int, ...], tyro.conf.arg(custom_constructor=...)]


Usage:
`python ./10_custom_constructors.py --help`
`python ./10_custom_constructors.py --dict1.json "{\"hello\": \"world\"}"`
`python ./10_custom_constructors.py --dict1.json "{\"hello\": \"world\"}"`  --dict2.json "{\"hello\": \"world\"}"`
"""

import json as json_

from typing_extensions import Annotated

import tyro


def dict_json_constructor(json: str) -> dict:
    """Construct a dictionary from a JSON string. Raises a ValueError if the result is
    not a dictionary."""
    out = json_.loads(json)
    if not isinstance(out, dict):
        raise ValueError(f"{json} is not a dictionary!")
    return out


# A dictionary type, but `tyro` will expect a JSON string from the CLI.
JsonDict = Annotated[dict, tyro.conf.arg(constructor=dict_json_constructor)]


def main(
    dict1: JsonDict,
    dict2: JsonDict = {"default": None},
) -> None:
    print(f"{dict1=}")
    print(f"{dict2=}")


if __name__ == "__main__":
    tyro.cli(main)
