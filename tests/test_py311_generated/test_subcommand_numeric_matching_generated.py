"""Tests for subcommand default matching with numeric type coercion.

Regression tests for:
1. int values should match float type annotations (numeric tower).
2. none-type should not appear in error messages from subcommand_type_from_defaults.
"""

import dataclasses
from typing import Tuple

import pytest

import tyro


@dataclasses.dataclass
class Optimizer:
    lr: float = 1.0


@dataclasses.dataclass
class Config:
    optimizers: dict[str, Optimizer]


def test_subcommand_int_matching_float() -> None:
    """int default values should match float type annotations."""
    result = tyro.cli(
        tyro.extras.subcommand_type_from_defaults(
            {
                "a": Config({"embeddings": Optimizer(lr=1)}),
                "b": Config({"embeddings": Optimizer(lr=2)}),
            }
        ),
        default=Config({"embeddings": Optimizer(lr=3)}),
        args=[],
    )
    assert isinstance(result, Config)


def test_subcommand_int_matching_float_select_a() -> None:
    """Selecting subcommand 'a' should work with int defaults for float fields."""
    result = tyro.cli(
        tyro.extras.subcommand_type_from_defaults(
            {
                "a": Config({"embeddings": Optimizer(lr=1)}),
                "b": Config({"embeddings": Optimizer(lr=2)}),
            }
        ),
        default=Config({"embeddings": Optimizer(lr=3)}),
        args=["a"],
    )
    assert isinstance(result, Config)
    # The overall default (lr=3) overrides the subcommand's default (lr=1).
    assert result.optimizers["embeddings"].lr == 3


@dataclasses.dataclass
class TupleConfig:
    point: Tuple[float, float] = (0.0, 0.0)


def test_subcommand_tuple_float_with_int_defaults() -> None:
    """tuple[float, float] fields with int default values should match."""
    result = tyro.cli(
        tyro.extras.subcommand_type_from_defaults(
            {
                "a": TupleConfig(point=(1, 2)),
                "b": TupleConfig(point=(2, 3)),
                "c": TupleConfig(point=(3, 4)),
            }
        ),
        default=TupleConfig(point=(1, 2)),
        args=[],
    )
    assert isinstance(result, TupleConfig)


def test_subcommand_tuple_float_with_int_defaults_select() -> None:
    """Selecting a specific subcommand with int defaults for float tuple fields."""
    result = tyro.cli(
        tyro.extras.subcommand_type_from_defaults(
            {
                "a": TupleConfig(point=(1, 2)),
                "b": TupleConfig(point=(2, 3)),
                "c": TupleConfig(point=(3, 4)),
            }
        ),
        default=TupleConfig(point=(1, 2)),
        args=["b"],
    )
    assert isinstance(result, TupleConfig)
    assert result.point == (2.0, 3.0)


def test_subcommand_tuple_float_with_int_defaults_override() -> None:
    """Overriding tuple[float, float] values via CLI args."""
    result = tyro.cli(
        tyro.extras.subcommand_type_from_defaults(
            {
                "a": TupleConfig(point=(1, 2)),
                "b": TupleConfig(point=(2, 3)),
                "c": TupleConfig(point=(3, 4)),
            }
        ),
        default=TupleConfig(point=(1, 2)),
        args=["c", "--point", "5.0", "6.0"],
    )
    assert isinstance(result, TupleConfig)
    assert result.point == (5.0, 6.0)


@dataclasses.dataclass
class NestedTupleConfig:
    params: dict[str, TupleConfig]


def test_subcommand_nested_tuple_float_with_int_defaults() -> None:
    """Nested dict with tuple[float, float] fields and int defaults should match."""
    result = tyro.cli(
        tyro.extras.subcommand_type_from_defaults(
            {
                "a": NestedTupleConfig(params={"layer1": TupleConfig(point=(1, 2))}),
                "b": NestedTupleConfig(params={"layer1": TupleConfig(point=(2, 3))}),
            }
        ),
        default=NestedTupleConfig(params={"layer1": TupleConfig(point=(3, 4))}),
        args=[],
    )
    assert isinstance(result, NestedTupleConfig)


@dataclasses.dataclass
class StrictConfig:
    """Config where passing wrong-typed defaults causes structural mismatch."""

    name: str = "hello"


def test_subcommand_unmatched_default_no_none_type_in_error(capsys) -> None:
    """When no subcommand matches the default, the error should not mention none-type.

    Regression test: subcommand_type_from_defaults pads with Annotated[None, Suppress]
    for single-element unions. This padding should not appear in error messages.
    """
    # Create a default where the field value has the wrong type (int for str field).
    # The type of the instance matches (StrictConfig), but the field value doesn't
    # pass structural matching.
    bad_default = StrictConfig(name=42)  # type: ignore
    with pytest.raises(SystemExit):
        tyro.cli(
            tyro.extras.subcommand_type_from_defaults(
                {
                    "good": StrictConfig(name="world"),
                }
            ),
            default=bad_default,
            args=[],
        )
    captured = capsys.readouterr()
    assert "none-type" not in captured.err, (
        "Suppressed NoneType padding should not appear in error messages"
    )
    assert "good" in captured.err, "Real subcommand should appear in error"


def test_subcommand_multi_unmatched_default_no_none_type_in_error(capsys) -> None:
    """When no subcommand matches, none-type should not appear even with multiple subcommands."""
    bad_default = StrictConfig(name=42)  # type: ignore
    with pytest.raises(SystemExit):
        tyro.cli(
            tyro.extras.subcommand_type_from_defaults(
                {
                    "x": StrictConfig(name="a"),
                    "y": StrictConfig(name="b"),
                }
            ),
            default=bad_default,
            args=[],
        )
    captured = capsys.readouterr()
    assert "none-type" not in captured.err
    # Real subcommands should still appear in the error.
    assert "x" in captured.err
    assert "y" in captured.err
