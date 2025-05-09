import enum
import pathlib
from datetime import date, datetime, time
from typing import Generic, List, Optional, Set, Tuple, TypeVar, Union

import msgspec
import pytest
from helptext_utils import get_helptext_with_checks
from typing_extensions import Annotated

import tyro
import tyro._strings
from tyro.conf import Positional, Suppress, arg


def test_basic_msgspec_struct():
    class User(msgspec.Struct):
        name: str
        age: int = 25
        email: Optional[str] = None

    # Test with all fields
    result = tyro.cli(
        User, args=["--name", "Alice", "--age", "30", "--email", "alice@example.com"]
    )
    assert result.name == "Alice"
    assert result.age == 30
    assert result.email == "alice@example.com"

    # Test with defaults
    result = tyro.cli(User, args=["--name", "Bob"])
    assert result.name == "Bob"
    assert result.age == 25  # default value
    assert result.email is None  # default value


def test_msgspec_struct_with_collections():
    class Config(msgspec.Struct):
        tags: List[str] = []
        flags: Set[int] = set()

    # Test with empty collections
    result = tyro.cli(Config, args=[])
    assert result.tags == []
    assert result.flags == set()

    # Test with populated collections
    result = tyro.cli(Config, args=["--tags", "tag1", "tag2", "--flags", "1", "2", "3"])
    assert result.tags == ["tag1", "tag2"]
    assert result.flags == {1, 2, 3}


def test_msgspec_struct_with_default_factory():
    class Settings(msgspec.Struct):
        values: List[str] = msgspec.field(default_factory=lambda: ["default"])

    # Test with default factory
    result = tyro.cli(Settings, args=[])
    assert result.values == ["default"]

    # Test with custom values
    result = tyro.cli(Settings, args=["--values", "custom1", "custom2"])
    assert result.values == ["custom1", "custom2"]


def test_msgspec_struct_validation():
    class Point(msgspec.Struct):
        x: int
        y: int

    # Test valid input
    result = tyro.cli(Point, args=["--x", "10", "--y", "20"])
    assert result.x == 10
    assert result.y == 20

    # Test invalid input (missing required field)
    with pytest.raises(SystemExit):
        tyro.cli(Point, args=["--x", "10"])

    # Test invalid input (wrong type)
    with pytest.raises(SystemExit):
        tyro.cli(Point, args=["--x", "10.5", "--y", "20"])


def test_nested_msgspec_struct():
    class Address(msgspec.Struct):
        street: str
        city: str
        zip_code: str

    class Person(msgspec.Struct):
        name: str
        address: Address

    # Test nested struct
    result = tyro.cli(
        Person,
        args=[
            "--name",
            "John",
            "--address.street",
            "123 Main St",
            "--address.city",
            "Boston",
            "--address.zip_code",
            "02108",
        ],
    )
    assert result.name == "John"
    assert result.address.street == "123 Main St"
    assert result.address.city == "Boston"
    assert result.address.zip_code == "02108"


def test_msgspec_struct_inheritance():
    class Animal(msgspec.Struct):
        name: str
        age: int = 0
        species: str = "unknown"

    class Dog(Animal):
        breed: str = "mixed"
        is_good_boy: bool = True

    class WorkingDog(Dog):
        job: str = "guard"
        hours_per_day: int = 8

    # Test base class
    result = tyro.cli(Animal, args=["--name", "Generic"])
    assert result.name == "Generic"
    assert result.age == 0
    assert result.species == "unknown"

    # Test single inheritance
    result = tyro.cli(Dog, args=["--name", "Rex", "--breed", "German Shepherd"])
    assert result.name == "Rex"
    assert result.age == 0  # inherited default
    assert result.species == "unknown"  # inherited default
    assert result.breed == "German Shepherd"
    assert result.is_good_boy is True  # inherited default

    # Test multiple inheritance
    result = tyro.cli(
        WorkingDog,
        args=[
            "--name",
            "Max",
            "--breed",
            "Belgian Malinois",
            "--job",
            "police",
            "--hours_per_day",
            "10",
        ],
    )
    assert result.name == "Max"
    assert result.age == 0  # inherited from Animal
    assert result.species == "unknown"  # inherited from Animal
    assert result.breed == "Belgian Malinois"  # inherited from Dog
    assert result.is_good_boy is True  # inherited from Dog
    assert result.job == "police"
    assert result.hours_per_day == 10


def test_msgspec_struct_with_datetime_types():
    class Event(msgspec.Struct):
        name: str
        start_time: datetime
        event_date: date
        check_in: time

    # Test with all datetime types
    result = tyro.cli(
        Event,
        args=[
            "--name",
            "Conference",
            "--start-time",
            "2024-03-20T09:00:00",
            "--event-date",
            "2024-03-20",
            "--check-in",
            "08:30:00",
        ],
    )
    assert result.name == "Conference"
    assert result.start_time == datetime(2024, 3, 20, 9, 0)
    assert result.event_date == date(2024, 3, 20)
    assert result.check_in == time(8, 30)


def test_msgspec_struct_with_enums():
    class Color(enum.Enum):
        RED = enum.auto()
        GREEN = enum.auto()
        BLUE = enum.auto()

    class Priority(enum.IntEnum):
        LOW = enum.auto()
        MEDIUM = enum.auto()
        HIGH = enum.auto()

    class Task(msgspec.Struct):
        name: str
        color: Color
        priority: Priority
        status: str = "pending"

    # Test with enum types
    result = tyro.cli(
        Task,
        args=[
            "--name",
            "Important Task",
            "--color",
            "RED",
            "--priority",
            "HIGH",
        ],
    )
    assert result.name == "Important Task"
    assert result.color == Color.RED
    assert result.priority == Priority.HIGH
    assert result.status == "pending"

    # Test invalid enum value
    with pytest.raises(SystemExit):
        tyro.cli(
            Task, args=["--name", "Task", "--color", "YELLOW", "--priority", "HIGH"]
        )


def test_msgspec_with_post_init_validation():
    class Interval(msgspec.Struct):
        start: int
        end: int

        def __post_init__(self):
            if self.start > self.end:
                raise ValueError("start must be less than or equal to end")

    # Test with valid values
    result = tyro.cli(Interval, args=["--start", "10", "--end", "20"])
    assert result.start == 10
    assert result.end == 20

    # Test with invalid values
    with pytest.raises(ValueError, match="start must be less than or equal to end"):
        tyro.cli(Interval, args=["--start", "30", "--end", "20"])


def test_msgspec_with_meta_validation():
    class Constraints(msgspec.Struct):
        name: Annotated[str, msgspec.Meta(min_length=3, max_length=50)]
        age: Annotated[int, msgspec.Meta(gt=0, lt=120)]
        score: Annotated[float, msgspec.Meta(ge=0.0, le=100.0)] = 0.0
        tags: Annotated[List[str], msgspec.Meta(min_length=1)] = msgspec.field(
            default_factory=lambda: ["default"]
        )

    # Test with valid values
    result = tyro.cli(
        Constraints,
        args=[
            "--name",
            "Alice",
            "--age",
            "25",
            "--score",
            "95.5",
            "--tags",
            "tag1",
            "tag2",
        ],
    )
    assert result.name == "Alice"
    assert result.age == 25
    assert result.score == 95.5
    assert result.tags == ["tag1", "tag2"]

    # Post-init validation is not triggered during CLI parsing for Meta constraints
    # It would only happen during deserialization
    # Test with defaults
    result = tyro.cli(Constraints, args=["--name", "Bob", "--age", "30"])
    assert result.name == "Bob"
    assert result.age == 30
    assert result.score == 0.0
    assert result.tags == ["default"]


def test_msgspec_with_path_conversion():
    class FileConfig(msgspec.Struct):
        config_path: pathlib.Path
        output_dir: pathlib.Path = pathlib.Path("./output")

    # Test with path values
    result = tyro.cli(FileConfig, args=["--config-path", "~/config.yaml"])
    assert result.config_path == pathlib.Path("~/config.yaml")
    assert result.output_dir == pathlib.Path("./output")

    # Test with custom output dir
    result = tyro.cli(
        FileConfig,
        args=["--config-path", "/etc/config.yaml", "--output-dir", "/var/log"],
    )
    assert result.config_path == pathlib.Path("/etc/config.yaml")
    assert result.output_dir == pathlib.Path("/var/log")


def test_msgspec_with_union_type():
    class UnionConfig(msgspec.Struct):
        value: Union[int, str] = "default"

    # Test with default
    result = tyro.cli(UnionConfig, args=[])
    assert result.value == "default"

    # Test with int
    result = tyro.cli(UnionConfig, args=["--value", "42"])
    assert result.value == 42

    # Test with str
    result = tyro.cli(UnionConfig, args=["--value", "hello"])
    assert result.value == "hello"


def test_msgspec_with_tuple_type():
    class TupleConfig(msgspec.Struct):
        coords: Tuple[float, float] = (0.0, 0.0)

    # Test with default
    result = tyro.cli(TupleConfig, args=[])
    assert result.coords == (0.0, 0.0)

    # Test with custom values
    result = tyro.cli(TupleConfig, args=["--coords", "1.5", "2.5"])
    assert result.coords == (1.5, 2.5)


def test_msgspec_with_positional():
    class PositionalConfig(msgspec.Struct):
        command: Positional[str]
        verbose: bool = False

    # Test with positional arg
    result = tyro.cli(PositionalConfig, args=["run"])
    assert result.command == "run"
    assert result.verbose is False

    # Test with positional and flag
    result = tyro.cli(PositionalConfig, args=["test", "--verbose"])
    assert result.command == "test"
    assert result.verbose is True


def test_msgspec_with_suppress():
    class ConfigWithSuppressed(msgspec.Struct):
        visible: str
        hidden: Suppress[str] = "secret"

    # Test with visible field
    result = tyro.cli(ConfigWithSuppressed, args=["--visible", "hello"])
    assert result.visible == "hello"
    assert result.hidden == "secret"  # Should still have the default value

    # Verify hidden field is not in helptext
    helptext = get_helptext_with_checks(ConfigWithSuppressed)
    assert "--visible" in helptext
    assert "--hidden" not in helptext


def test_msgspec_with_aliases():
    class AliasConfig(msgspec.Struct):
        long_option: Annotated[str, arg(aliases=["-l"])]
        another_option: Annotated[int, arg(aliases=["--alt", "-a"])] = 0

    # Test with long form
    result = tyro.cli(AliasConfig, args=["--long-option", "value"])
    assert result.long_option == "value"
    assert result.another_option == 0

    # Test with short form
    result = tyro.cli(AliasConfig, args=["-l", "value", "-a", "42"])
    assert result.long_option == "value"
    assert result.another_option == 42

    # Test with alternate form
    result = tyro.cli(AliasConfig, args=["-l", "value", "--alt", "42"])
    assert result.long_option == "value"
    assert result.another_option == 42


def test_msgspec_helptext():
    class Helptext(msgspec.Struct):
        """This docstring should be printed as a description."""

        x: int
        """Documentation for x."""

        y: int
        """Documentation for y."""

        z: int = 42
        """Documentation for z."""

    # Check that the docstrings are included in the helptext
    helptext = get_helptext_with_checks(Helptext)
    assert "This docstring should be printed as a description" in helptext
    assert "Documentation for x" in helptext
    assert "Documentation for y" in helptext
    assert "Documentation for z" in helptext


def test_msgspec_with_field_metadata():
    class ExplicitMetadata(msgspec.Struct):
        name: str
        """The name of the user."""

        age: int
        """The age of the user."""

        tags: List[str] = msgspec.field(default_factory=list)
        """User tags."""

    # Check that field metadata is included in helptext
    helptext = get_helptext_with_checks(ExplicitMetadata)
    assert "The name of the user" in helptext
    assert "The age of the user" in helptext
    assert "User tags" in helptext


# Define TypeVar for generic tests
T = TypeVar("T")
S = TypeVar("S")


def test_msgspec_with_generics():
    class GenericStruct(msgspec.Struct, Generic[T]):
        value: T
        name: str = "generic"

    # Test with int type
    result = tyro.cli(GenericStruct[int], args=["--value", "42"])
    assert result.value == 42
    assert result.name == "generic"

    # Test with str type
    result = tyro.cli(GenericStruct[str], args=["--value", "hello"])
    assert result.value == "hello"
    assert result.name == "generic"

    # Test with float type
    result = tyro.cli(GenericStruct[float], args=["--value", "3.14"])
    assert result.value == 3.14
    assert result.name == "generic"


def test_msgspec_with_multiple_generics():
    class MultiGenericStruct(msgspec.Struct, Generic[T, S]):
        t_value: T
        s_value: S
        name: str = "multi-generic"

    # Test with int, str combination
    result = tyro.cli(
        MultiGenericStruct[int, str], args=["--t-value", "42", "--s-value", "hello"]
    )
    assert result.t_value == 42
    assert result.s_value == "hello"
    assert result.name == "multi-generic"


def test_msgspec_default_instance():
    class Inside(msgspec.Struct, frozen=True):  # Must be frozen for mutable default
        x: int = 1

    class Outside(msgspec.Struct):
        i: Inside = Inside(x=2)

    assert tyro.cli(Outside, args=[]).i.x == 2, (
        "Expected x value from the default instance"
    )
    assert tyro.cli(Outside, args=["--i.x", "3"]).i.x == 3


def test_msgspec_nested_default_instance():
    class Inside(msgspec.Struct, frozen=True):  # Must be frozen
        x: int = 1

    class Middle(msgspec.Struct, frozen=True):  # Must be frozen
        i: Inside = Inside(x=2)

    class Outside(msgspec.Struct):
        m: Middle = Middle(i=Inside(x=2))

    assert tyro.cli(Outside, args=[]).m.i.x == 2, (
        "Expected x value from the default instance"
    )
    assert tyro.cli(Outside, args=["--m.i.x", "3"]).m.i.x == 3
