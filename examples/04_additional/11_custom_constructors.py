"""Custom Constructors

For additional flexibility, :module:`tyro.constructors` exposes
tyro's API for defining behavior for different types. This is the same
API that tyro relies on for the built-in types.

Usage:
`python ./10_custom_constructors.py --help`
`python ./10_custom_constructors.py --dict1.json '{"hello": "world"}'`
`python ./10_custom_constructors.py --dict1.json "{\"hello\": \"world\"}"`
`python ./10_custom_constructors.py --dict1.json '{"hello": "world"}' --dict2.json '{"hello": "world"}'`
`python ./10_custom_constructors.py --dict1.json "{\"hello\": \"world\"}" --dict2.json "{\"hello\": \"world\"}"`
"""

import json

from typing_extensions import Annotated

import tyro

# A dictionary type, but `tyro` will expect a JSON string from the CLI.
JsonDict = Annotated[
    dict,
    tyro.constructors.PrimitiveConstructorSpec(
        nargs=1,
        metavar="JSON",
        instance_from_str=lambda args: json.loads(args[0]),
        is_instance=lambda instance: isinstance(instance, dict),
        str_from_instance=lambda instance: [json.dumps(instance)],
    ),
]


def main(
    dict1: JsonDict,
    dict2: JsonDict = {"default": None},
) -> None:
    print(f"{dict1=}")
    print(f"{dict2=}")


if __name__ == "__main__":
    tyro.cli(main)
