"""Dictionary inputs can be specified using a TypedDict type.

TODO: note that setting total=False is not yet (but could be) supported."""

from typing import TypedDict

import dcargs


class DictionarySchema(TypedDict):
    field1: str  # A string field.
    field2: int  # A numeric field.
    field3: bool  # A boolean field.


if __name__ == "__main__":
    x = dcargs.cli(DictionarySchema)
    assert isinstance(x, dict)
    print(x)
