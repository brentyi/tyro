# mypy: ignore-errors
"""Tests for self-referential (recursive) dataclass types."""

from __future__ import annotations

import contextlib
import dataclasses
import io

import pytest

import tyro
import tyro._strings


@dataclasses.dataclass(frozen=True)
class InferenceConfig:
    name: str = "Hello"
    secondary: InferenceConfig | None = None


@dataclasses.dataclass(frozen=True)
class Node:
    value: int = 0
    left: Node | None = None
    right: Node | None = None


def _skip_if_argparse(backend: str) -> None:
    """The argparse backend hits infinite recursion on self-referential types."""
    if backend == "argparse":
        pytest.skip("recursive structs are tyro-backend only")


def _get_helptext(
    f,
    args: list[str] = ["--help"],
    config: tuple = (),
) -> str:
    """Get helptext without running completion checks (which also recurse infinitely)."""
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(f, args=args, config=config)
    return tyro._strings.strip_ansi_sequences(target.getvalue())


# --- Basic recursive struct tests ---


def test_recursive_default(backend: str):
    _skip_if_argparse(backend)
    assert tyro.cli(InferenceConfig, args=[]) == InferenceConfig(
        name="Hello", secondary=None
    )


def test_recursive_set_name(backend: str):
    _skip_if_argparse(backend)
    assert tyro.cli(InferenceConfig, args=["--name", "World"]) == InferenceConfig(
        name="World", secondary=None
    )


def test_recursive_one_level(backend: str):
    _skip_if_argparse(backend)
    result = tyro.cli(
        InferenceConfig,
        args=[
            "--name",
            "Outer",
            "secondary:inference-config",
            "--secondary.name",
            "Inner",
        ],
    )
    assert result == InferenceConfig(
        name="Outer",
        secondary=InferenceConfig(name="Inner", secondary=None),
    )


def test_recursive_one_level_default_secondary_name(backend: str):
    """Nested level should use its own defaults when not overridden."""
    _skip_if_argparse(backend)
    result = tyro.cli(
        InferenceConfig,
        args=["--name", "Outer", "secondary:inference-config"],
    )
    assert result == InferenceConfig(
        name="Outer",
        secondary=InferenceConfig(name="Hello", secondary=None),
    )


def test_recursive_two_levels(backend: str):
    _skip_if_argparse(backend)
    result = tyro.cli(
        InferenceConfig,
        args=[
            "--name",
            "L0",
            "secondary:inference-config",
            "--secondary.name",
            "L1",
            "secondary.secondary:inference-config",
            "--secondary.secondary.name",
            "L2",
        ],
    )
    assert result == InferenceConfig(
        name="L0",
        secondary=InferenceConfig(
            name="L1",
            secondary=InferenceConfig(name="L2", secondary=None),
        ),
    )


def test_recursive_three_levels(backend: str):
    _skip_if_argparse(backend)
    result = tyro.cli(
        InferenceConfig,
        args=[
            "--name",
            "L0",
            "secondary:inference-config",
            "--secondary.name",
            "L1",
            "secondary.secondary:inference-config",
            "--secondary.secondary.name",
            "L2",
            "secondary.secondary.secondary:inference-config",
            "--secondary.secondary.secondary.name",
            "L3",
        ],
    )
    assert result == InferenceConfig(
        name="L0",
        secondary=InferenceConfig(
            name="L1",
            secondary=InferenceConfig(
                name="L2",
                secondary=InferenceConfig(name="L3", secondary=None),
            ),
        ),
    )


def test_recursive_four_levels(backend: str):
    _skip_if_argparse(backend)
    result = tyro.cli(
        InferenceConfig,
        args=[
            "--name",
            "L0",
            "secondary:inference-config",
            "--secondary.name",
            "L1",
            "secondary.secondary:inference-config",
            "--secondary.secondary.name",
            "L2",
            "secondary.secondary.secondary:inference-config",
            "--secondary.secondary.secondary.name",
            "L3",
            "secondary.secondary.secondary.secondary:inference-config",
            "--secondary.secondary.secondary.secondary.name",
            "L4",
        ],
    )
    assert result == InferenceConfig(
        name="L0",
        secondary=InferenceConfig(
            name="L1",
            secondary=InferenceConfig(
                name="L2",
                secondary=InferenceConfig(
                    name="L3",
                    secondary=InferenceConfig(name="L4", secondary=None),
                ),
            ),
        ),
    )


def test_recursive_four_levels_terminate_with_none(backend: str):
    """Four levels deep, explicitly terminating the chain with :none."""
    _skip_if_argparse(backend)
    result = tyro.cli(
        InferenceConfig,
        args=[
            "secondary:inference-config",
            "secondary.secondary:inference-config",
            "secondary.secondary.secondary:inference-config",
            "secondary.secondary.secondary.secondary:none",
        ],
    )
    assert result == InferenceConfig(
        name="Hello",
        secondary=InferenceConfig(
            name="Hello",
            secondary=InferenceConfig(
                name="Hello",
                secondary=InferenceConfig(name="Hello", secondary=None),
            ),
        ),
    )


def test_recursive_select_none(backend: str):
    _skip_if_argparse(backend)
    result = tyro.cli(
        InferenceConfig,
        args=["secondary:none"],
    )
    assert result == InferenceConfig(name="Hello", secondary=None)


def test_recursive_helptext(backend: str):
    _skip_if_argparse(backend)
    helptext = _get_helptext(InferenceConfig)
    assert "secondary:inference-config" in helptext
    assert "secondary:none" in helptext
    assert "--name" in helptext


def test_recursive_invalid_args(backend: str):
    _skip_if_argparse(backend)
    with pytest.raises(SystemExit):
        tyro.cli(InferenceConfig, args=["--nonexistent", "value"])


# --- Binary tree (multiple recursive fields) ---


def test_recursive_binary_tree_default(backend: str):
    _skip_if_argparse(backend)
    assert tyro.cli(Node, args=[]) == Node(value=0, left=None, right=None)


def test_recursive_binary_tree_one_child(backend: str):
    _skip_if_argparse(backend)
    result = tyro.cli(
        Node,
        args=[
            "--value",
            "1",
            "left:node",
            "--left.value",
            "2",
        ],
    )
    assert result == Node(
        value=1,
        left=Node(value=2, left=None, right=None),
        right=None,
    )


def test_recursive_binary_tree_both_children(backend: str):
    _skip_if_argparse(backend)
    result = tyro.cli(
        Node,
        args=[
            "--value",
            "1",
            "left:node",
            "--left.value",
            "2",
            "right:node",
            "--right.value",
            "3",
        ],
    )
    assert result == Node(
        value=1,
        left=Node(value=2, left=None, right=None),
        right=Node(value=3, left=None, right=None),
    )


def test_recursive_binary_tree_nested(backend: str):
    """Tree with a grandchild node."""
    _skip_if_argparse(backend)
    result = tyro.cli(
        Node,
        args=[
            "--value",
            "1",
            "left:node",
            "--left.value",
            "2",
            "left.left:node",
            "--left.left.value",
            "4",
        ],
    )
    assert result == Node(
        value=1,
        left=Node(
            value=2,
            left=Node(value=4, left=None, right=None),
            right=None,
        ),
        right=None,
    )


def test_recursive_binary_tree_helptext(backend: str):
    _skip_if_argparse(backend)
    helptext = _get_helptext(Node)
    assert "left:node" in helptext
    assert "left:none" in helptext
    assert "right:node" in helptext
    assert "right:none" in helptext


# --- Default instances ---


def test_recursive_with_default_instance(backend: str):
    _skip_if_argparse(backend)
    default = InferenceConfig(
        name="DefaultOuter",
        secondary=InferenceConfig(name="DefaultInner", secondary=None),
    )
    result = tyro.cli(InferenceConfig, args=[], default=default)
    assert result == default


def test_recursive_with_default_instance_override(backend: str):
    _skip_if_argparse(backend)
    default = InferenceConfig(
        name="DefaultOuter",
        secondary=InferenceConfig(name="DefaultInner", secondary=None),
    )
    result = tyro.cli(
        InferenceConfig,
        args=["--name", "Overridden"],
        default=default,
    )
    assert result.name == "Overridden"
    assert result.secondary == InferenceConfig(name="DefaultInner", secondary=None)


def test_recursive_with_deep_default_instance(backend: str):
    """Default instance with 3 levels of nesting should round-trip."""
    _skip_if_argparse(backend)
    default = InferenceConfig(
        name="L0",
        secondary=InferenceConfig(
            name="L1",
            secondary=InferenceConfig(name="L2", secondary=None),
        ),
    )
    result = tyro.cli(InferenceConfig, args=[], default=default)
    assert result == default


# --- Tests with CascadeSubcommandArgs ---


def test_recursive_cascade_default(backend: str):
    _skip_if_argparse(backend)
    result = tyro.cli(
        InferenceConfig,
        args=[],
        config=(tyro.conf.CascadeSubcommandArgs,),
    )
    assert result == InferenceConfig(name="Hello", secondary=None)


def test_recursive_cascade_one_level(backend: str):
    _skip_if_argparse(backend)
    result = tyro.cli(
        InferenceConfig,
        args=[
            "--name",
            "Outer",
            "secondary:inference-config",
            "--secondary.name",
            "Inner",
        ],
        config=(tyro.conf.CascadeSubcommandArgs,),
    )
    assert result == InferenceConfig(
        name="Outer",
        secondary=InferenceConfig(name="Inner", secondary=None),
    )


def test_recursive_cascade_one_level_inner_default(backend: str):
    """With CascadeSubcommandArgs, the inner level should use its own default."""
    _skip_if_argparse(backend)
    result = tyro.cli(
        InferenceConfig,
        args=["--name", "Outer", "secondary:inference-config"],
        config=(tyro.conf.CascadeSubcommandArgs,),
    )
    assert result == InferenceConfig(
        name="Outer",
        secondary=InferenceConfig(name="Hello", secondary=None),
    )


def test_recursive_cascade_two_levels(backend: str):
    _skip_if_argparse(backend)
    result = tyro.cli(
        InferenceConfig,
        args=[
            "--name",
            "L0",
            "secondary:inference-config",
            "--secondary.name",
            "L1",
            "secondary.secondary:inference-config",
            "--secondary.secondary.name",
            "L2",
        ],
        config=(tyro.conf.CascadeSubcommandArgs,),
    )
    assert result == InferenceConfig(
        name="L0",
        secondary=InferenceConfig(
            name="L1",
            secondary=InferenceConfig(name="L2", secondary=None),
        ),
    )


def test_recursive_cascade_three_levels(backend: str):
    _skip_if_argparse(backend)
    result = tyro.cli(
        InferenceConfig,
        args=[
            "--name",
            "L0",
            "secondary:inference-config",
            "--secondary.name",
            "L1",
            "secondary.secondary:inference-config",
            "--secondary.secondary.name",
            "L2",
            "secondary.secondary.secondary:inference-config",
            "--secondary.secondary.secondary.name",
            "L3",
        ],
        config=(tyro.conf.CascadeSubcommandArgs,),
    )
    assert result == InferenceConfig(
        name="L0",
        secondary=InferenceConfig(
            name="L1",
            secondary=InferenceConfig(
                name="L2",
                secondary=InferenceConfig(name="L3", secondary=None),
            ),
        ),
    )


def test_recursive_cascade_four_levels(backend: str):
    _skip_if_argparse(backend)
    result = tyro.cli(
        InferenceConfig,
        args=[
            "--name",
            "L0",
            "secondary:inference-config",
            "--secondary.name",
            "L1",
            "secondary.secondary:inference-config",
            "--secondary.secondary.name",
            "L2",
            "secondary.secondary.secondary:inference-config",
            "--secondary.secondary.secondary.name",
            "L3",
            "secondary.secondary.secondary.secondary:inference-config",
            "--secondary.secondary.secondary.secondary.name",
            "L4",
        ],
        config=(tyro.conf.CascadeSubcommandArgs,),
    )
    assert result == InferenceConfig(
        name="L0",
        secondary=InferenceConfig(
            name="L1",
            secondary=InferenceConfig(
                name="L2",
                secondary=InferenceConfig(
                    name="L3",
                    secondary=InferenceConfig(name="L4", secondary=None),
                ),
            ),
        ),
    )


def test_recursive_cascade_helptext(backend: str):
    _skip_if_argparse(backend)
    helptext = _get_helptext(
        InferenceConfig,
        config=(tyro.conf.CascadeSubcommandArgs,),
    )
    assert "secondary:inference-config" in helptext
    assert "secondary:none" in helptext
    assert "--name" in helptext
