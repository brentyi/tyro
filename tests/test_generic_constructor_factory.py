from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel
from typing_extensions import Annotated

import tyro


class AThing(BaseModel):
    a: int


TContainsAThing = TypeVar("TContainsAThing", bound=AThing)


class GenericThingManager(Generic[TContainsAThing]):
    @classmethod
    def spam(
        cls,
        thing2: TContainsAThing,
        thing: Annotated[
            TContainsAThing | list[TContainsAThing],
            tyro.conf.arg(constructor_factory=lambda: TContainsAThing),  # type: ignore
        ],
    ) -> tuple[TContainsAThing, TContainsAThing]:
        return thing2, thing  # type: ignore

    @classmethod
    def eggs(
        cls,
        thing: Annotated[
            TContainsAThing | list[TContainsAThing],
            tyro.conf.arg(constructor_factory=lambda: TContainsAThing),  # type: ignore
        ],
    ) -> TContainsAThing:
        return thing  # type: ignore


class ABThing(AThing):
    b: str


class ABThingManager(GenericThingManager[ABThing]):
    pass


def test_generic_constructor_factory_spam():
    """Test that spam subcommand works with generic constructor factory."""
    # Test with single ABThing instance.
    thing2, thing = tyro.cli(
        ABThingManager.spam,
        args=[
            "--thing2.a",
            "1",
            "--thing2.b",
            "foo",
            "--thing.a",
            "2",
            "--thing.b",
            "bar",
        ],
    )
    assert isinstance(thing2, ABThing)
    assert thing2.a == 1
    assert thing2.b == "foo"
    assert isinstance(thing, ABThing)
    assert thing.a == 2
    assert thing.b == "bar"


def test_generic_constructor_factory_eggs():
    """Test that eggs subcommand works with generic constructor factory."""
    # Test with single ABThing instance.
    thing = tyro.cli(
        ABThingManager.eggs,
        args=["--thing.a", "3", "--thing.b", "baz"],
    )
    assert isinstance(thing, ABThing)
    assert thing.a == 3
    assert thing.b == "baz"


def test_generic_constructor_factory_subcommand_cli():
    """Test subcommand CLI with generic constructor factory."""
    # Test spam subcommand.
    thing2, thing = tyro.extras.subcommand_cli_from_dict(
        {
            "spam": ABThingManager.spam,
            "eggs": ABThingManager.eggs,
        },
        args=[
            "spam",
            "--thing2.a",
            "1",
            "--thing2.b",
            "hello",
            "--thing.a",
            "2",
            "--thing.b",
            "world",
        ],
    )
    assert isinstance(thing2, ABThing)
    assert thing2.a == 1
    assert thing2.b == "hello"
    assert isinstance(thing, ABThing)
    assert thing.a == 2
    assert thing.b == "world"

    # Test eggs subcommand.
    thing = tyro.extras.subcommand_cli_from_dict(
        {
            "spam": ABThingManager.spam,
            "eggs": ABThingManager.eggs,
        },
        args=["eggs", "--thing.a", "4", "--thing.b", "test"],
    )
    assert isinstance(thing, ABThing)
    assert thing.a == 4
    assert thing.b == "test"
