"""Tests for nested subparsers functionality."""

import dataclasses
from typing import Annotated, Union

import pytest

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


def test_unnamed_nested_union_flattens():
    """Unnamed nested unions should flatten into a single level."""
    # Union[A, Union[B, C]] without name should become Union[A, B, C].
    typ = Union[CommandA, Annotated[Union[CommandB, CommandC], None]]

    # All three commands should be available at the top level.
    assert tyro.cli(typ, args=["command-a", "--x", "1", "--y", "hello"]) == CommandA(1, "hello")
    assert tyro.cli(typ, args=["command-b", "--a", "2.5", "--b", "True"]) == CommandB(2.5, True)
    assert tyro.cli(typ, args=["command-c", "--p", "1", "2", "--q", "k", "3"]) == CommandC([1, 2], {"k": 3})


def test_named_nested_union_creates_hierarchy():
    """Named nested unions should create a hierarchical subparser structure."""
    # Union[A, Union[B, C]] with name should create nested structure.
    typ = Union[
        CommandA,
        Annotated[Union[CommandB, CommandC], tyro.conf.subcommand(name="group_bc")]
    ]

    # CommandA should be at top level.
    assert tyro.cli(typ, args=["command-a", "--x", "1", "--y", "hello"]) == CommandA(1, "hello")

    # CommandB and CommandC should be under group_bc.
    assert tyro.cli(typ, args=["group_bc", "command-b", "--a", "2.5", "--b", "True"]) == CommandB(2.5, True)
    assert tyro.cli(typ, args=["group_bc", "command-c", "--p", "1", "2", "--q", "k:3"]) == CommandC([1, 2], {"k": 3})


def test_deeply_nested_unions():
    """Test 3+ levels of nesting with mixed named/unnamed unions."""
    # Create a 3-level hierarchy:
    # Top level: command-a or group-rest
    # group-rest: command-b or group-cde
    # group-cde: command-c, command-d, or command-e
    typ = Union[
        CommandA,
        Annotated[
            Union[
                CommandB,
                Annotated[
                    Union[CommandC, CommandD, CommandE],
                    tyro.conf.subcommand(name="group_cde")
                ]
            ],
            tyro.conf.subcommand(name="group_rest")
        ]
    ]

    # Test each path through the hierarchy.
    assert tyro.cli(typ, args=["command-a", "--x", "1", "--y", "hello"]) == CommandA(1, "hello")
    assert tyro.cli(typ, args=["group-rest", "command-b", "--a", "2.5", "--b", "true"]) == CommandB(2.5, True)
    assert tyro.cli(typ, args=["group-rest", "group-cde", "command-c", "--p", "1", "--q", "k:3"]) == CommandC([1], {"k": 3})
    assert tyro.cli(typ, args=["group-rest", "group-cde", "command-d", "--value", "test"]) == CommandD("test")
    assert tyro.cli(typ, args=["group-rest", "group-cde", "command-e", "--count", "42"]) == CommandE(42)


def test_mixed_named_unnamed_nested_unions():
    """Test mixing named and unnamed nested unions - unnamed should flatten into parent."""
    # Create mixed structure:
    # Top: command-a or group_bc or command-d (command-d flattened from unnamed union)
    typ = Union[
        CommandA,
        Annotated[Union[CommandB, CommandC], tyro.conf.subcommand(name="group_bc")],
        Annotated[Union[CommandD], None],  # Unnamed, should flatten.
    ]

    # command-a and command-d at top level, command-b and command-c under group_bc.
    assert tyro.cli(typ, args=["command-a", "--x", "1", "--y", "hello"]) == CommandA(1, "hello")
    assert tyro.cli(typ, args=["command-d", "--value", "test"]) == CommandD("test")
    assert tyro.cli(typ, args=["group_bc", "command-b", "--a", "2.5", "--b", "True"]) == CommandB(2.5, True)
    assert tyro.cli(typ, args=["group_bc", "command-c", "--p", "1", "--q", "k:3"]) == CommandC([1], {"k": 3})


def test_multiple_named_groups_at_same_level():
    """Test multiple named subparser groups at the same level."""
    typ = Union[
        Annotated[Union[CommandA, CommandB], tyro.conf.subcommand(name="group_ab")],
        Annotated[Union[CommandC, CommandD], tyro.conf.subcommand(name="group_cd")],
    ]

    assert tyro.cli(typ, args=["group-ab", "command-a", "--x", "1", "--y", "hello"]) == CommandA(1, "hello")
    assert tyro.cli(typ, args=["group-ab", "command-b", "--a", "2.5", "--b", "true"]) == CommandB(2.5, True)
    assert tyro.cli(typ, args=["group-cd", "command-c", "--p", "1", "--q", "k:3"]) == CommandC([1], {"k": 3})
    assert tyro.cli(typ, args=["group-cd", "command-d", "--value", "test"]) == CommandD("test")


def test_helptext_for_nested_subparsers():
    """Test that help text is generated correctly for nested structures."""
    typ = Union[
        CommandA,
        Annotated[
            Union[CommandB, CommandC],
            tyro.conf.subcommand(name="bc_commands", description="Commands B and C")
        ]
    ]

    # Test that we can get help without errors.
    with pytest.raises(SystemExit):
        tyro.cli(typ, args=["--help"])

    with pytest.raises(SystemExit):
        tyro.cli(typ, args=["bc-commands", "--help"])

    with pytest.raises(SystemExit):
        tyro.cli(typ, args=["bc-commands", "command-b", "--help"])


def test_defaults_in_nested_subparsers():
    """Test that defaults work correctly in nested subparser structures."""
    typ = Union[
        CommandA,
        Annotated[
            Union[CommandB, CommandC],
            tyro.conf.subcommand(name="bc_group", default=CommandB(1.0, False))
        ]
    ]

    # With default, bc-group should be optional.
    # This might need adjustment based on how defaults are handled.
    result = tyro.cli(typ, args=[])
    assert result == CommandB(1.0, False)

    # Can still override the default.
    assert tyro.cli(typ, args=["command-a", "--x", "1", "--y", "hi"]) == CommandA(1, "hi")
    assert tyro.cli(typ, args=["bc-group", "command-c", "--p", "1", "--q", "k:2"]) == CommandC([1], {"k": 2})


def test_single_union_with_name():
    """A single-element union with a name should still create a subparser level."""
    typ = Union[
        CommandA,
        Annotated[Union[CommandB], tyro.conf.subcommand(name="b_only")]
    ]

    assert tyro.cli(typ, args=["command-a", "--x", "1", "--y", "hello"]) == CommandA(1, "hello")
    assert tyro.cli(typ, args=["b-only", "command-b", "--a", "2.5", "--b", "true"]) == CommandB(2.5, True)


def test_avoid_subcommands_with_nested_unions():
    """Test interaction with tyro.conf.AvoidSubcommands."""
    typ = Union[
        Annotated[CommandA, tyro.conf.AvoidSubcommands],
        Annotated[
            Union[CommandB, CommandC],
            tyro.conf.subcommand(name="bc_group")
        ]
    ]

    # CommandA should not require a subcommand name due to AvoidSubcommands.
    assert tyro.cli(typ, args=["--x", "1", "--y", "hello"], default=CommandA(0, "")) == CommandA(1, "hello")

    # command-b and command-c should still be under bc-group.
    assert tyro.cli(typ, args=["bc-group", "command-b", "--a", "2.5", "--b", "true"]) == CommandB(2.5, True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
