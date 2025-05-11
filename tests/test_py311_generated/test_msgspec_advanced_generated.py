from typing import (
    Dict,
    FrozenSet,
    Generic,
    List,
    Literal,
    NewType,
    Optional,
    Set,
    TypeVar,
)

import msgspec
import pytest
from helptext_utils import get_helptext_with_checks

import tyro

# Define TypeVars for generics tests
T = TypeVar("T")
S = TypeVar("S")
U = TypeVar("U", bound=float)

# Define NewType for testing
UserId = NewType("UserId", int)


def test_msgspec_with_complex_generics():
    """Test msgspec structs with complex generic parameters."""

    class Container(msgspec.Struct, Generic[T]):
        value: T
        name: str = "container"

    class NestedContainer(msgspec.Struct, Generic[T, S]):
        outer: Container[T]
        inner_value: S
        description: str = "nested"

    # Test with int, str combination
    result = tyro.cli(
        NestedContainer[int, str],
        args=[
            "--outer.value",
            "42",
            "--outer.name",
            "custom",
            "--inner-value",
            "hello",
        ],
    )
    assert result.outer.value == 42
    assert result.outer.name == "custom"
    assert result.inner_value == "hello"
    assert result.description == "nested"

    # Test with defaults
    result = tyro.cli(
        NestedContainer[float, bool],
        args=["--outer.value", "3.14", "--inner-value", "True"],
    )
    assert result.outer.value == 3.14
    assert result.outer.name == "container"  # default
    assert result.inner_value is True
    assert result.description == "nested"  # default


def test_msgspec_with_bound_typevars():
    """Test msgspec structs with bounded TypeVars."""

    class NumericValue(msgspec.Struct, Generic[U]):
        value: U
        name: str = "numeric"

    # Test with int (within bounds)
    result = tyro.cli(NumericValue[int], args=["--value", "42"])
    assert result.value == 42.0
    assert result.name == "numeric"

    # Test with float (within bounds)
    result = tyro.cli(NumericValue[float], args=["--value", "3.14"])
    assert result.value == 3.14
    assert result.name == "numeric"


def test_msgspec_with_generic_containers():
    """Test msgspec structs with generic container types."""

    class GenericListContainer(msgspec.Struct, Generic[T]):
        items: List[T]
        name: str = "list_container"

    # Test with list of strings
    result = tyro.cli(GenericListContainer[str], args=["--items", "a", "b", "c"])
    assert result.items == ["a", "b", "c"]
    assert result.name == "list_container"

    # Test with list of integers
    result = tyro.cli(GenericListContainer[int], args=["--items", "1", "2", "3"])
    assert result.items == [1, 2, 3]
    assert result.name == "list_container"


def test_msgspec_with_generic_union_types():
    """Test msgspec structs with Union types inside generics."""

    class GenericOptional(msgspec.Struct, Generic[T]):
        value: Optional[T] = None
        description: str = "optional"

    # Test with None (default)
    result = tyro.cli(GenericOptional[int], args=[])
    assert result.value is None

    # Test with int value
    result = tyro.cli(GenericOptional[int], args=["--value", "42"])
    assert result.value == 42

    # Test with str value
    result = tyro.cli(GenericOptional[str], args=["--value", "hello"])
    assert result.value == "hello"


def test_msgspec_with_literal_types():
    """Test msgspec structs with Literal types."""

    class ConfigMode(msgspec.Struct):
        mode: Literal["development", "production", "testing"] = "development"
        debug: bool = False

    # Test with default
    result = tyro.cli(ConfigMode, args=[])
    assert result.mode == "development"
    assert result.debug is False

    # Test with explicit mode
    result = tyro.cli(ConfigMode, args=["--mode", "production", "--debug"])
    assert result.mode == "production"
    assert result.debug is True

    # Test with invalid mode (should fail)
    with pytest.raises(SystemExit):
        tyro.cli(ConfigMode, args=["--mode", "invalid"])


def test_msgspec_with_newtype():
    """Test msgspec structs with NewType."""

    class User(msgspec.Struct):
        id: UserId
        name: str

    # Test with valid UserId
    result = tyro.cli(User, args=["--id", "12345", "--name", "John"])
    assert result.id == 12345
    assert isinstance(result.id, int)
    assert result.name == "John"


def test_msgspec_with_set_types():
    """Test msgspec structs with Set and FrozenSet types."""

    class SetContainer(msgspec.Struct):
        mutable_set: Set[int] = msgspec.field(default_factory=set)
        immutable_set: FrozenSet[str] = frozenset()

    # Test with default values
    result = tyro.cli(SetContainer, args=[])
    assert result.mutable_set == set()
    assert result.immutable_set == frozenset()

    # Test with custom values
    result = tyro.cli(
        SetContainer,
        args=["--mutable-set", "1", "2", "3", "--immutable-set", "a", "b", "c"],
    )
    assert result.mutable_set == {1, 2, 3}
    assert result.immutable_set == frozenset({"a", "b", "c"})


def test_msgspec_with_bytes():
    """Test msgspec structs with bytes and bytearray types."""

    class BinaryData(msgspec.Struct):
        data: bytes = b""

    # Test with default
    result = tyro.cli(BinaryData, args=[])
    assert result.data == b""

    # Test with string that gets converted to bytes
    # This relies on tyro's handling of bytes conversion
    result = tyro.cli(BinaryData, args=["--data", "hello"])
    assert result.data == b"hello"


def test_msgspec_with_dict():
    """Test msgspec structs with Dict type."""

    class DictContainer(msgspec.Struct):
        metadata: Dict[str, int] = msgspec.field(default_factory=dict)

    # Test with empty dict (default)
    result = tyro.cli(DictContainer, args=[])
    assert result.metadata == {}


def test_msgspec_with_generics_helptext():
    """Test helptext generation for generic msgspec structs."""

    class GenericConfig(msgspec.Struct, Generic[T]):
        """A generic configuration.

        This is used to configure generic values.
        """

        value: T
        """The generic value."""

        name: str = "config"
        """Configuration name."""

    # Verify helptext contains the docstrings
    helptext = get_helptext_with_checks(GenericConfig[int])
    assert "A generic configuration" in helptext
    assert "This is used to configure generic values" in helptext
    assert "The generic value" in helptext
    assert "Configuration name" in helptext

    # Verify the parameter type is shown correctly
    # For int instantiation
    helptext_int = get_helptext_with_checks(GenericConfig[int])
    assert "--value INT" in helptext_int

    # For str instantiation
    helptext_str = get_helptext_with_checks(GenericConfig[str])
    assert "--value STR" in helptext_str
