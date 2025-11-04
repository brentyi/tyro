"""Tests for nested subparsers functionality."""

from __future__ import annotations

import dataclasses
from typing import Any, Union

import pytest
from typing_extensions import Annotated

import tyro


@dataclasses.dataclass
class CommandA:
    x: int
    y: str


@dataclasses.dataclass
class CommandB:
    a: float
    b: bool


@dataclasses.dataclass
class CommandC:
    p: list[int]
    q: dict[str, int]


@dataclasses.dataclass
class CommandD:
    value: str


@dataclasses.dataclass
class CommandE:
    count: int


def test_unnamed_nested_union_flattens() -> None:
    """Unnamed nested unions should flatten into a single level."""
    typ: Any = Union[CommandA, Annotated[Union[CommandB, CommandC], None]]

    # All three commands should be available at the top level.
    assert tyro.cli(typ, args=["command-a", "--x", "1", "--y", "hello"]) == CommandA(
        1, "hello"
    )
    assert tyro.cli(
        typ,
        args=["union-command-b-command-c", "command-b", "--a", "2.5", "--b", "True"],
    ) == CommandB(2.5, True)
    assert tyro.cli(
        typ,
        args=[
            "union-command-b-command-c",
            "command-c",
            "--p",
            "1",
            "2",
            "--q",
            "k",
            "3",
        ],
    ) == CommandC([1, 2], {"k": 3})


def test_named_nested_union_creates_hierarchy() -> None:
    """Named nested unions should create a hierarchical subparser structure."""
    # Union[A, Union[B, C]] with name should create nested structure.
    typ: Any = Union[
        CommandA,
        Annotated[Union[CommandB, CommandC], tyro.conf.subcommand(name="group-bc")],
    ]

    # CommandA should be at top level.
    assert tyro.cli(typ, args=["command-a", "--x", "1", "--y", "hello"]) == CommandA(
        1, "hello"
    )

    # CommandB and CommandC should be under group-bc.
    assert tyro.cli(
        typ, args=["group-bc", "command-b", "--a", "2.5", "--b", "True"]
    ) == CommandB(2.5, True)
    assert tyro.cli(
        typ, args=["group-bc", "command-c", "--p", "1", "2", "--q", "k", "3"]
    ) == CommandC([1, 2], {"k": 3})


def test_deeply_nested_unions() -> None:
    """Test 3+ levels of nesting with mixed named/unnamed unions."""
    # Create a 3-level hierarchy:
    # Top level: command-a or group-rest
    # group-rest: command-b or group-cde
    # group-cde: command-c, command-d, or command-e
    typ: Any = Union[
        CommandA,
        Annotated[
            Union[
                CommandB,
                Annotated[
                    Union[CommandC, CommandD, CommandE],
                    tyro.conf.subcommand(name="group-cde"),
                ],
            ],
            tyro.conf.subcommand(name="group-rest"),
        ],
    ]

    # Test each path through the hierarchy.
    assert tyro.cli(typ, args=["command-a", "--x", "1", "--y", "hello"]) == CommandA(
        1, "hello"
    )
    assert tyro.cli(
        typ, args=["group-rest", "command-b", "--a", "2.5", "--b", "True"]
    ) == CommandB(2.5, True)
    assert tyro.cli(
        typ, args=["group-rest", "group-cde", "command-c", "--p", "1", "--q", "k", "3"]
    ) == CommandC([1], {"k": 3})
    assert tyro.cli(
        typ, args=["group-rest", "group-cde", "command-d", "--value", "test"]
    ) == CommandD("test")
    assert tyro.cli(
        typ, args=["group-rest", "group-cde", "command-e", "--count", "42"]
    ) == CommandE(42)


def test_mixed_named_unnamed_nested_unions() -> None:
    """Test mixing named and unnamed nested unions - unnamed should flatten into parent."""
    # Create mixed structure:
    # Top: command-a or group-bc or command-d (command-d flattened from unnamed union)
    typ: Any = Union[
        CommandA,
        Annotated[Union[CommandB, CommandC], tyro.conf.subcommand(name="group-bc")],
        Annotated[Union[CommandD], None],
    ]

    # command-a and command-d at top level, command-b and command-c under group-bc.
    assert tyro.cli(typ, args=["command-a", "--x", "1", "--y", "hello"]) == CommandA(
        1, "hello"
    )
    assert tyro.cli(typ, args=["command-d", "--value", "test"]) == CommandD("test")
    assert tyro.cli(
        typ, args=["group-bc", "command-b", "--a", "2.5", "--b", "True"]
    ) == CommandB(2.5, True)
    assert tyro.cli(
        typ, args=["group-bc", "command-c", "--p", "1", "--q", "k", "3"]
    ) == CommandC([1], {"k": 3})


def test_multiple_named_groups_at_same_level() -> None:
    """Test multiple named subparser groups at the same level."""
    # Workaround for: https://github.com/microsoft/pyright/issues/11046
    # Getting this to pass type checking after the test gen runs and converts
    # `Union[X, Y]` types to `X | Y` was trickier than expected...
    AorB: Any = Annotated[
        Union[CommandA, CommandB], tyro.conf.subcommand(name="group-ab")
    ]
    CorD: Any = Annotated[
        Union[CommandC, CommandD], tyro.conf.subcommand(name="group-cd")
    ]
    typ: Any = Union[AorB, CorD, CommandC]

    assert tyro.cli(
        typ, args=["group-ab", "command-a", "--x", "1", "--y", "hello"]
    ) == CommandA(1, "hello")
    assert tyro.cli(
        typ, args=["group-ab", "command-b", "--a", "2.5", "--b", "True"]
    ) == CommandB(2.5, True)
    assert tyro.cli(
        typ, args=["group-cd", "command-c", "--p", "1", "--q", "k", "3"]
    ) == CommandC([1], {"k": 3})
    assert tyro.cli(typ, args=["command-c", "--p", "1", "--q", "k", "3"]) == CommandC(
        [1], {"k": 3}
    )
    assert tyro.cli(typ, args=["group-cd", "command-d", "--value", "test"]) == CommandD(
        "test"
    )


def test_only_named_groups_at_same_level() -> None:
    """Test multiple named subparser groups at the same level."""
    # Workaround for: https://github.com/microsoft/pyright/issues/11046
    # Getting this to pass type checking after the test gen runs and converts
    # `Union[X, Y]` types to `X | Y` was trickier than expected...
    AorB: Any = Annotated[
        Union[CommandA, CommandB], tyro.conf.subcommand(name="group-ab")
    ]
    CorD: Any = Annotated[
        Union[CommandC, CommandD], tyro.conf.subcommand(name="group-cd")
    ]
    typ: Any = Union[AorB, CorD]

    assert tyro.cli(
        typ, args=["group-ab", "command-a", "--x", "1", "--y", "hello"]
    ) == CommandA(1, "hello")
    assert tyro.cli(
        typ, args=["group-ab", "command-b", "--a", "2.5", "--b", "True"]
    ) == CommandB(2.5, True)
    assert tyro.cli(
        typ, args=["group-cd", "command-c", "--p", "1", "--q", "k", "3"]
    ) == CommandC([1], {"k": 3})
    assert tyro.cli(typ, args=["group-cd", "command-d", "--value", "test"]) == CommandD(
        "test"
    )


def test_helptext_for_nested_subparsers() -> None:
    """Test that help text is generated correctly for nested structures."""
    typ: Any = Union[
        CommandA,
        Annotated[
            Union[CommandB, CommandC],
            tyro.conf.subcommand(name="bc-commands", description="Commands B and C"),
        ],
    ]

    # Test that we can get help without errors.
    with pytest.raises(SystemExit):
        tyro.cli(typ, args=["--help"])

    with pytest.raises(SystemExit):
        tyro.cli(typ, args=["bc-commands", "--help"])

    with pytest.raises(SystemExit):
        tyro.cli(typ, args=["bc-commands", "command-b", "--help"])


def test_defaults_in_nested_subparsers() -> None:
    """Test that defaults work correctly in nested subparser structures."""
    typ: Any = Union[
        CommandA,
        Annotated[Union[CommandB, CommandC], tyro.conf.subcommand(name="bc-group")],
    ]

    # With default, bc-group should be optional.
    # This might need adjustment based on how defaults are handled.
    result = tyro.cli(typ, args=[], default=CommandB(1.0, False))
    assert result == CommandB(1.0, False)

    # Can still override the default.
    assert tyro.cli(
        typ, args=["command-a", "--x", "1", "--y", "hi"], default=CommandB(1.0, False)
    ) == CommandA(1, "hi")
    assert tyro.cli(
        typ,
        args=["bc-group", "command-c", "--p", "1", "--q", "k", "2"],
        default=CommandB(1.0, False),
    ) == CommandC([1], {"k": 2})


def test_config_default_none_preserved() -> None:
    """A subcommand config default of None should propagate to the parsed value."""
    typ: Any = Union[CommandA, None]

    # No arguments selects the configured default of None.
    assert tyro.cli(typ, args=[], default=None) is None

    # Explicitly selecting CommandA still works.
    assert tyro.cli(
        typ, args=["command-a", "--x", "1", "--y", "hi"], default=None
    ) == CommandA(1, "hi")


def test_single_union_with_name() -> None:
    """A single-element union with a name creates an alias (no extra subparser level).

    Union[CommandB] is effectively the same as CommandB, so wrapping it in a named
    union just creates an alias for the subcommand rather than nesting."""
    typ: Any = Union[
        CommandA, Annotated[Union[CommandB], tyro.conf.subcommand(name="b-only")]
    ]

    assert tyro.cli(typ, args=["command-a", "--x", "1", "--y", "hello"]) == CommandA(
        1, "hello"
    )
    # Single-element union flattens: b-only directly takes CommandB's arguments.
    assert tyro.cli(typ, args=["b-only", "--a", "2.5", "--b", "True"]) == CommandB(
        2.5, True
    )
