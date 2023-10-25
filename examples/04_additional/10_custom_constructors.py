"""Custom Constructors

For additional flexibility, :func:`tyro.conf.arg()` accepts a `constructor` argument,
which makes it easier to load complex objects.

Usage:
`python ./10_custom_constructors.py --help`
`python ./10_custom_constructors.py --dict1.json "{\"hello\": \"world\"}"`
`python ./10_custom_constructors.py --dict1.json "{\"hello\": \"world\"}"`  --dict2.json "{\"hello\": \"world\"}"`
"""

import dataclasses
import json as json_
from typing import Dict

from typing_extensions import Annotated

import tyro


def dict_json_constructor(json: str) -> dict:
    """Construct a dictionary from a JSON string. Raises a ValueError if it fails."""
    out = json_.loads(json)
    if not isinstance(out, dict):
        raise ValueError(f"{json} is not a dictionary!")
    return out


# A dictionary type, but `tyro` will construct it with JSON.
JsonDict = Annotated[dict, tyro.conf.arg(constructor=dict_json_constructor)]


def main(
    dict1: JsonDict,
    dict2: JsonDict = {"default": None},
) -> None:
    print(dict1)
    print(dict2)


if __name__ == "__main__":
    tyro.cli(main)
