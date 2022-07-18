"""Dictionary inputs can be specified using either a standard `Dict[K, V]` annotation,
or a `TypedDict` type.

Note that setting `total=False` for `TypedDict` is currently not (but reasonably could be)
supported.

Usage:
`python ./11_dictionaries.py --help`
"""

from typing import Dict, Tuple, TypedDict

import dcargs


class DictionarySchema(TypedDict):
    learning_rate: float
    betas: Tuple[float, float]


def main(
    standard_dict: Dict[str, float] = {
        "learning_rate": 3e-4,
        "beta1": 0.9,
        "beta2": 0.999,
    },
    typed_dict: DictionarySchema = {
        "learning_rate": 3e-4,
        "betas": (0.9, 0.999),
    },
) -> None:
    assert isinstance(standard_dict, dict)
    assert isinstance(typed_dict, dict)
    print("Standard dict:", standard_dict)
    print("Typed dict:", typed_dict)


if __name__ == "__main__":
    dcargs.cli(main)
