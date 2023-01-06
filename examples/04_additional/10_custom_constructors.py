"""TODO:

Usage:
`python ./10_custom_constructors.py --help`
`python ./10_custom_constructors.py --food fruit`
`python ./10_custom_constructors.py --food vegetable`
"""

import functools
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
    # TODO: this example is temporary. We should make it more readable.
    tyro.registry.register_constructor(
        matcher=lambda typ: typ is Food,
        constructor_factory=lambda typ, default: make_food
        # If a default is provided (consider: def main(food: Food = Vegetable())), how
        # should we handle it?
        #
        # TODO: do we need to expose both propagating and non-propagating missing types?
        # This is surprisingly annoying : - )
        if default in tyro._fields.MISSING_SINGLETONS
        else functools.partial(
            make_food, food="fruit" if isinstance(default, Fruit) else "vegetable"
        ),
    )

    # Note that `Food` is a protocol and cannot be directly instantiated; we
    # must instead rely on an external factory function.
    food = tyro.cli(Food)
    food.eat()
