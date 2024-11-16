"""Custom Primitive

In this example, we use :mod:`tyro.constructors` to attach a primitive
constructor via a runtime annotation.

Usage:

    python ./02_primitive_annotation.py --help
    python ./02_primitive_annotation.py --dict1 '{"hello": "world"}'
    python ./02_primitive_annotation.py --dict1 '{"hello": "world"}' --dict2 '{"hello": "world"}'
"""

import json

from typing_extensions import Annotated

import tyro

# A dictionary type, but `tyro` will expect a JSON string from the CLI.
JsonDict = Annotated[
    dict,
    tyro.constructors.PrimitiveConstructorSpec(
        # Number of arguments to consume.
        nargs=1,
        # Argument name in usage messages.
        metavar="JSON",
        # Convert a list of strings to an instance. The length of the list
        # should match `nargs`.
        instance_from_str=lambda args: json.loads(args[0]),
        # Check if an instance is of the expected type. This is only used for
        # helptext formatting in the presence of union types.
        is_instance=lambda instance: isinstance(instance, dict),
        # Convert an instance to a list of strings. This is used for handling
        # default values that are set in Python. The length of the list should
        # match `nargs`.
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
