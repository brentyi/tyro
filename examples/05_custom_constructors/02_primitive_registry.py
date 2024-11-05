"""Custom Primitive (Registry)
For additional flexibility, :mod:`tyro.constructors` exposes tyro's API for
defining behavior for different types. There are two categories of types:
primitive types can be instantiated from a single commandline argument, while
struct types are broken down into multiple.


In this example, we attach a custom constructor by defining a rule that applies
to all types that match ``dict[str, Any]``.

Usage:
`python ./02_primitive_registry.py --help`
`python ./02_primitive_registry.py --dict1 '{"hello": "world"}'`
`python ./02_primitive_registry.py --dict1 '{"hello": "world"}' --dict2 '{"hello": "world"}'`
"""

import json
from typing import Any

import tyro

custom_registry = tyro.constructors.ConstructorRegistry()


@custom_registry.primitive_rule
def _(
    type_info: tyro.constructors.PrimitiveTypeInfo,
) -> tyro.constructors.PrimitiveConstructorSpec | None:
    # We return `None` if the rule does not apply.
    if type_info.type != dict[str, Any]:
        return None

    # If the rule applies, we return the constructor spec.
    return tyro.constructors.PrimitiveConstructorSpec(
        nargs=1,
        metavar="JSON",
        instance_from_str=lambda args: json.loads(args[0]),
        is_instance=lambda instance: isinstance(instance, dict),
        str_from_instance=lambda instance: [json.dumps(instance)],
    )


def main(
    dict1: dict[str, Any],
    dict2: dict[str, Any] = {"default": None},
) -> None:
    print(f"{dict1=}")
    print(f"{dict2=}")


if __name__ == "__main__":
    with custom_registry:
        tyro.cli(main)