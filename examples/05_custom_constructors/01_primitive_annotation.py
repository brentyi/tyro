"""Custom Primitive

For additional flexibility, :mod:`tyro.constructors` exposes tyro's API for
defining behavior for different types. There are two categories of types:
primitive types can be instantiated from a single commandline argument, while
struct types are broken down into multiple.

In this example, we attach a custom constructor via a runtime annotation.

Usage:
`python ./01_primitive_annotation.py --help`
`python ./01_primitive_annotation.py --dict1 '{"hello": "world"}'`
`python ./01_primitive_annotation.py --dict1 '{"hello": "world"}' --dict2 '{"hello": "world"}'`
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
