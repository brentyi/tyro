"""Custom Structs (Registry)

In this example, we use a :class:`tyro.constructors.ConstructorRegistry` to
add support for a custom struct type. Each struct type is broken down into
multiple fields, which themselves can be either primitive types or nested
structs.

.. warning::

    This will be complicated!

Usage:
    python ./04_struct_registry.py --help
    python ./04_struct_registry.py --bounds.lower 5 --bounds.upper 10
"""

import tyro


# A custom type that we'll add support for to tyro.
class Bounds:
    def __init__(self, lower: int, upper: int):
        self.bounds = (lower, upper)

    def __repr__(self) -> str:
        return f"(lower={self.bounds[0]}, upper={self.bounds[1]})"


# Create a custom registry, which stores constructor rules.
custom_registry = tyro.constructors.ConstructorRegistry()


# Define a rule that applies to all types that match `Bounds`.
@custom_registry.struct_rule
def _(
    type_info: tyro.constructors.StructTypeInfo,
) -> tyro.constructors.StructConstructorSpec | None:
    # We return `None` if the rule does not apply.
    if type_info.type != Bounds:
        return None

    # We can extract the default value of the field from `type_info`.
    if isinstance(type_info.default, Bounds):
        # If the default value is a `Bounds` instance, we don't need to generate a constructor.
        default = (type_info.default.bounds[0], type_info.default.bounds[1])
    else:
        # Otherwise, the default value is missing. We'll mark the child defaults as missing as well.
        assert type_info.default in (
            tyro.constructors.MISSING,
            tyro.constructors.MISSING_NONPROP,
        )
        default = (tyro.MISSING, tyro.MISSING)

    # If the rule applies, we return the constructor spec.
    return tyro.constructors.StructConstructorSpec(
        # The instantiate function will be called with the fields as keyword arguments.
        instantiate=Bounds,
        fields=(
            tyro.constructors.StructFieldSpec(
                name="lower",
                type=int,
                default=default[0],
                helptext="Lower bound.",
            ),
            tyro.constructors.StructFieldSpec(
                name="upper",
                type=int,
                default=default[1],
                helptext="Upper bound.",
            ),
        ),
    )


def main(
    bounds: Bounds,
    bounds_with_default: Bounds = Bounds(0, 100),
) -> None:
    """A function with two `Bounds` instances as input."""
    print(f"{bounds=}")
    print(f"{bounds_with_default=}")


if __name__ == "__main__":
    # Pass the registry directly to tyro.cli().
    tyro.cli(main, registry=custom_registry)
