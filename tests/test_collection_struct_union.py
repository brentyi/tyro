"""Tests for collection[Struct] in unions creating proper subcommands.

This verifies that when collections (dict, list, tuple) have non-primitive values
and appear in a union, tyro correctly recognizes them as struct types and creates
subcommands.

Important: Collection types in unions require explicit defaults. Without a default,
even in a union context, they will error. This is consistent with tyro's philosophy
that standalone List[Struct], Dict[str, Struct], etc. require defaults.

Examples:
- List[Struct] | None           → ERROR (no default for list variant)
- List[Struct] | None = None    → ERROR (None doesn't provide default for list)
- List[Struct] | None = []      → OK (explicit empty list default)
- List[Struct] | None = [...]   → OK (explicit list default)
"""

import dataclasses
from typing import Dict, List, Optional, Tuple, Union

import pytest

import tyro


def test_dict_struct_union_with_none() -> None:
    """Test that dict[str, Struct] | None creates subcommands."""

    @dataclasses.dataclass
    class Config:
        x: int
        y: int

    @dataclasses.dataclass
    class Args:
        # Creates subcommands for dict vs None.
        configs: Optional[Dict[str, Config]] = dataclasses.field(
            default_factory=lambda: {
                "a": Config(x=1, y=2),
                "b": Config(x=3, y=4),
            }
        )

    # Test default case (should use the dict variant).
    result = tyro.cli(Args, args=[])
    assert result.configs == {"a": Config(x=1, y=2), "b": Config(x=3, y=4)}

    # Test explicit dict subcommand with modified values.
    result = tyro.cli(
        Args,
        args=[
            "configs:dict-str-config",
            "--configs.a.x",
            "10",
            "--configs.b.y",
            "20",
        ],
    )
    assert result.configs == {"a": Config(x=10, y=2), "b": Config(x=3, y=20)}

    # Test None subcommand.
    result = tyro.cli(Args, args=["configs:none"])
    assert result.configs is None


def test_dict_struct_empty_default_union() -> None:
    """Test that dict[str, Struct] | None with empty default creates subcommands."""

    @dataclasses.dataclass
    class Config:
        x: int
        y: str

    @dataclasses.dataclass
    class Args:
        # Empty default - should still recognize as struct type.
        configs: Optional[Dict[str, Config]] = dataclasses.field(default_factory=dict)

    # Test None subcommand.
    result = tyro.cli(Args, args=["configs:none"])
    assert result.configs is None

    # With empty default dict provided.
    result = tyro.cli(Args, args=["configs:dict-str-config"])
    assert result.configs == {}


def test_dict_struct_union_with_other_type() -> None:
    """Test that dict[str, Struct] in union with other types creates subcommands."""

    @dataclasses.dataclass
    class Config:
        value: int

    @dataclasses.dataclass
    class AlternativeConfig:
        name: str

    @dataclasses.dataclass
    class Args:
        data: Union[Dict[str, Config], AlternativeConfig] = dataclasses.field(
            default_factory=lambda: {"default": Config(value=5)}
        )

    # Test default (dict variant).
    result = tyro.cli(Args, args=[])
    assert result.data == {"default": Config(value=5)}

    # Test dict subcommand.
    result = tyro.cli(Args, args=["data:dict-str-config", "--data.default.value", "10"])
    assert result.data == {"default": Config(value=10)}

    # Test alternative config subcommand.
    result = tyro.cli(Args, args=["data:alternative-config", "--data.name", "test"])
    assert result.data == AlternativeConfig(name="test")


def test_nested_dict_struct() -> None:
    """Test that regular dict[str, Struct] (without union) still unpacks normally."""

    @dataclasses.dataclass
    class Config:
        x: int
        y: int

    @dataclasses.dataclass
    class Args:
        # Without union, should unpack the dict fields normally.
        configs: Dict[str, Config] = dataclasses.field(
            default_factory=lambda: {
                "a": Config(x=1, y=2),
                "b": Config(x=3, y=4),
            }
        )

    # Test that nested fields are accessible directly.
    result = tyro.cli(
        Args,
        args=["--configs.a.x", "10", "--configs.b.y", "20"],
    )
    assert result.configs == {"a": Config(x=10, y=2), "b": Config(x=3, y=20)}

    # Test default.
    result = tyro.cli(Args, args=[])
    assert result.configs == {"a": Config(x=1, y=2), "b": Config(x=3, y=4)}


def test_list_struct_union_with_other_type2() -> None:
    """Test that list[Struct] with non-empty default in union with struct works."""

    @dataclasses.dataclass
    class Config:
        value: int

    @dataclasses.dataclass
    class AlternativeConfig:
        name: str

    @dataclasses.dataclass
    class Args:
        # Non-empty list default in union with another struct type.
        data: Union[List[Config], AlternativeConfig] = dataclasses.field(
            default_factory=lambda: [Config(value=5), Config(value=10)]
        )

    # Test default (list variant).
    result = tyro.cli(Args, args=[])
    assert result.data == [Config(value=5), Config(value=10)]

    # Test list subcommand.
    result = tyro.cli(Args, args=["data:list-config", "--data.0.value", "100"])
    assert result.data == [Config(value=100), Config(value=10)]

    # Test alternative config subcommand.
    result = tyro.cli(Args, args=["data:alternative-config", "--data.name", "test2"])
    assert result.data == AlternativeConfig(name="test2")


def test_list_struct_union_with_none_nonempty_default() -> None:
    """Test that list[Struct] | None with non-empty default creates subcommands."""

    @dataclasses.dataclass
    class Config:
        value: int

    @dataclasses.dataclass
    class Args:
        # Non-empty default in union with None.
        data: Optional[List[Config]] = dataclasses.field(
            default_factory=lambda: [Config(value=5), Config(value=10)]
        )

    # Test default (list variant).
    result = tyro.cli(Args, args=[])
    assert result.data == [Config(value=5), Config(value=10)]

    # Test list subcommand with modified values.
    result = tyro.cli(Args, args=["data:list-config", "--data.0.value", "100"])
    assert result.data == [Config(value=100), Config(value=10)]

    # Test None subcommand.
    result = tyro.cli(Args, args=["data:none"])
    assert result.data is None


def test_list_struct_union_with_none_empty_default() -> None:
    """Test that list[Struct] | None with empty default creates subcommands."""

    @dataclasses.dataclass
    class Config:
        value: int

    @dataclasses.dataclass
    class Args:
        # Empty default in union with None.
        data: Optional[List[Config]] = dataclasses.field(default_factory=list)

    # Test None subcommand.
    result = tyro.cli(Args, args=["data:none"])
    assert result.data is None

    # Test list subcommand with empty list.
    result = tyro.cli(Args, args=["data:list-config"])
    assert result.data == []


def test_tuple_struct_union_with_other_type() -> None:
    """Test that tuple[Struct, ...] with non-empty default in union with struct works."""

    @dataclasses.dataclass
    class Config:
        value: int

    @dataclasses.dataclass
    class AlternativeConfig:
        name: str

    @dataclasses.dataclass
    class Args:
        # Non-empty tuple default in union with another struct type.
        data: Union[Tuple[Config, ...], AlternativeConfig] = dataclasses.field(
            default_factory=lambda: (Config(value=5), Config(value=10))
        )

    # Test default (tuple variant).
    result = tyro.cli(Args, args=[])
    assert result.data == (Config(value=5), Config(value=10))

    # Test tuple subcommand.
    result = tyro.cli(
        Args, args=["data:tuple-config-ellipsis", "--data.0.value", "100"]
    )
    assert result.data == (Config(value=100), Config(value=10))

    # Test alternative config subcommand.
    result = tyro.cli(Args, args=["data:alternative-config", "--data.name", "test2"])
    assert result.data == AlternativeConfig(name="test2")


def test_tuple_struct_union_with_none_nonempty_default() -> None:
    """Test that tuple[Struct, ...] | None with non-empty default creates subcommands."""

    @dataclasses.dataclass
    class Config:
        value: int

    @dataclasses.dataclass
    class Args:
        # Non-empty default in union with None.
        data: Optional[Tuple[Config, ...]] = dataclasses.field(
            default_factory=lambda: (Config(value=5), Config(value=10))
        )

    # Test default (tuple variant).
    result = tyro.cli(Args, args=[])
    assert result.data == (Config(value=5), Config(value=10))

    # Test tuple subcommand with modified values.
    result = tyro.cli(
        Args, args=["data:tuple-config-ellipsis", "--data.0.value", "100"]
    )
    assert result.data == (Config(value=100), Config(value=10))

    # Test None subcommand.
    result = tyro.cli(Args, args=["data:none"])
    assert result.data is None


def test_tuple_struct_union_with_none_empty_default() -> None:
    """Test that tuple[Struct, ...] | None with empty default creates subcommands."""

    @dataclasses.dataclass
    class Config:
        value: int

    @dataclasses.dataclass
    class Args:
        # Empty default in union with None.
        data: Optional[Tuple[Config, ...]] = dataclasses.field(default_factory=tuple)

    # Test None subcommand.
    result = tyro.cli(Args, args=["data:none"])
    assert result.data is None

    # Test tuple subcommand with empty tuple.
    result = tyro.cli(Args, args=["data:tuple-config-ellipsis"])
    assert result.data == ()


def test_list_struct_union_with_other_type() -> None:
    """Test that list[Struct] in union with other types creates subcommands."""

    @dataclasses.dataclass
    class Config:
        value: int

    @dataclasses.dataclass
    class AlternativeConfig:
        name: str

    @dataclasses.dataclass
    class Args:
        data: Union[List[Config], AlternativeConfig] = dataclasses.field(
            default_factory=lambda: [Config(value=5)]
        )

    # Test default (list variant).
    result = tyro.cli(Args, args=[])
    assert result.data == [Config(value=5)]

    # Test list subcommand.
    result = tyro.cli(Args, args=["data:list-config", "--data.0.value", "10"])
    assert result.data == [Config(value=10)]

    # Test alternative config subcommand.
    result = tyro.cli(Args, args=["data:alternative-config", "--data.name", "test"])
    assert result.data == AlternativeConfig(name="test")


def test_list_struct_union_no_default_errors() -> None:
    """Test that List[Struct] | None without default raises an error.

    This verifies that we require explicit defaults even in union contexts,
    maintaining consistency with standalone collection types.
    """

    @dataclasses.dataclass
    class Config:
        value: int

    @dataclasses.dataclass
    class Args:
        # No default - should error!
        data: Optional[List[Config]]

    # Should raise SystemExit when trying to use the list variant.
    with pytest.raises(SystemExit):
        tyro.cli(Args, args=["data:list-config"])


def test_dict_struct_union_no_default_errors() -> None:
    """Test that Dict[str, Struct] | None without default raises an error."""

    @dataclasses.dataclass
    class Config:
        value: int

    @dataclasses.dataclass
    class Args:
        # No default - should error!
        data: Optional[Dict[str, Config]]

    # Should raise SystemExit when trying to use the dict variant.
    with pytest.raises(SystemExit):
        tyro.cli(Args, args=["data:dict-str-config"])


def test_tuple_struct_union_no_default_errors() -> None:
    """Test that Tuple[Struct, ...] | None without default raises an error."""

    @dataclasses.dataclass
    class Config:
        value: int

    @dataclasses.dataclass
    class Args:
        # No default - should error!
        data: Optional[Tuple[Config, ...]]

    # Should raise SystemExit when trying to use the tuple variant.
    with pytest.raises(SystemExit):
        tyro.cli(Args, args=["data:tuple-config-ellipsis"])
