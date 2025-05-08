import msgspec
import pytest
from typing import Optional, List, Set
from datetime import datetime, date, time
import enum

import tyro


def test_basic_msgspec_struct():
    class User(msgspec.Struct):
        name: str
        age: int = 25
        email: Optional[str] = None

    # Test with all fields
    result = tyro.cli(User, args=["--name", "Alice", "--age", "30", "--email", "alice@example.com"])
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
        def default_list() -> List[str]:
            return ["default"]

        values: List[str] = msgspec.field(default_factory=default_list)

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
        tyro.cli(Task, args=["--name", "Task", "--color", "YELLOW", "--priority", "HIGH"])
