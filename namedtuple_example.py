from collections import namedtuple
from typing import NamedTuple

import tyro

# Example using collections.namedtuple
SomeType = namedtuple("SomeType", ("field1", "field2", "field3"))
try:
    # Without a default value, CLI arguments are parsed as strings
    tyro.cli(
        SomeType,
        args=["--field1", "3", "--field2", "4", "--field3", "5"],
    )
    assert False, (
        "Expected a TypeError due to missing default value, we can't infer types"
    )
except tyro.constructors.UnsupportedTypeAnnotationError:
    pass


# With a default value, tyro can infer types (int in this case)
assert tyro.cli(
    SomeType,
    default=SomeType(0, 1, 2),
    args=["--field1", "3", "--field2", "4"],
) == SomeType(3, 4, 2)


# Example using typing.NamedTuple (already supported)
class TypedSomeType(NamedTuple):
    field1: int
    field2: int
    field3: int


# Type annotations ensure correct parsing
assert tyro.cli(
    TypedSomeType,
    args=["--field1", "3", "--field2", "4", "--field3", "5"],
) == TypedSomeType(3, 4, 5)

# Default values work as expected
assert tyro.cli(
    TypedSomeType,
    default=TypedSomeType(0, 1, 2),
    args=["--field1", "3", "--field2", "4"],
) == TypedSomeType(3, 4, 2)
