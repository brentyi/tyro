"""Dictionary inputs can be specified using either a standard `Dict[K, V]` annotation,
or a `TypedDict` type.

Note that setting `total=False` for `TypedDict` is currently not (but reasonably could be)
supported.

Usage:
`python ./11_dictionaries.py --help`
`python ./11_dictionaries.py --standard-dict key1 True key2 False`
"""

from typing import Dict, TypedDict

import dcargs


class DictionarySchema(TypedDict):
    field1: str  # A string field.
    field2: int  # A numeric field.
    field3: bool  # A boolean field.


def main(
    standard_dict: Dict[str, bool],
    typed_dict: DictionarySchema = {
        "field1": "hey",
        "field2": 3,
        "field3": False,
    },
) -> None:
    assert isinstance(standard_dict, dict)
    assert isinstance(typed_dict, dict)
    print("Standard dict:", standard_dict)
    print("Typed dict:", typed_dict)


if __name__ == "__main__":
    dcargs.cli(main)
