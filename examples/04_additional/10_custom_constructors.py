"""TODO:

Usage:
`python ./10_custom_constructors.py --help`
`python ./10_custom_constructors.py --food fruit`
`python ./10_custom_constructors.py --food vegetable`
"""

from typing import Literal, Protocol

from typing_extensions import assert_never

import tyro

# Implement a `Food` protocol and two structural subtypes: `Fruit` and `Vegetable`.


class Food(Protocol):
    """Interface for defining food objects, which can be eaten."""

    def eat(self) -> None:
        ...


class Fruit:
    def eat(self) -> None:
        print("Ate a fruit!")


class Vegetable:
    def eat(self) -> None:
        print("Ate a vegetable!")


# Define a custom constructor for instantiating `Food` objects.


def make_food(food: Literal["fruit", "vegetable"]) -> Food:
    """Make a food.

    Args:
        food: Type of food.

    Returns:
        A food object.
    """
    if food == "fruit":
        return Fruit()
    elif food == "vegetable":
        return Vegetable()
    else:
        assert_never(food)


if __name__ == "__main__":
    tyro.registry.register_constructor(
        matcher=lambda typ: typ is Food,
        constructor_factory=lambda typ: make_food,
    )

    # Note that `Food` is a protocol and cannot be directly instantiated; we
    # must instead rely on an external factory function.
    food = tyro.cli(Food)
    food.eat()
