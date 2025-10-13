from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Annotated

import tyro


@dataclass
class Dataclass:
    a: int
    b: str = "default"


@dataclass
class Config:
    x: Annotated[
        Dataclass | None,
        tyro.conf.arg(
            constructor=tyro.extras.subcommand_type_from_defaults(
                {
                    "none": None,
                    "dc": Dataclass(3),
                }
            )
        ),
    ] = None


def test_simple() -> None:
    """Check for edge case where the `None` type in the union is annotated with
    metadata."""
    assert tyro.cli(Config, args=[]) == Config(None)


def test_simple2() -> None:
    """Check for edge case where the `None` type in the union is annotated with
    metadata."""
    assert tyro.cli(Config, args=["x:none"]) == Config(None)


def test_simple3() -> None:
    """Check for edge case where the `None` type in the union is annotated with
    metadata."""
    assert tyro.cli(Config, args=["x:dc"]) == Config(Dataclass(3))


def test_simple4() -> None:
    """Check for edge case where the `None` type in the union is annotated with
    metadata."""
    assert tyro.cli(Config, args=["x:dc", "--x.a", "5"]) == Config(Dataclass(5))
