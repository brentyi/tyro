"""Overriding Dictionaries

Dictionary inputs can be specified using either a standard `Dict[K, V]` annotation, or a
`TypedDict` subclass.

Usage:
`python ./02_dictionaries.py --help`
`python ./02_dictionaries.py --typed-dict.learning-rate 3e-4`
`python ./02_dictionaries.py --typed-dict.betas 0.9 0.999`
"""

from typing import Dict, Tuple, TypedDict

from typing_extensions import NotRequired

import tyro


class DictionarySchemaA(
    TypedDict,
    # Setting `total=False` specifies that not all keys need to exist.
    total=False,
):
    learning_rate: float
    betas: Tuple[float, float]


class DictionarySchemaB(TypedDict):
    learning_rate: NotRequired[float]
    """NotRequired[] specifies that a particular key doesn't need to exist."""
    betas: Tuple[float, float]


def main(
    typed_dict_a: DictionarySchemaA,
    typed_dict_b: DictionarySchemaB,
    standard_dict: Dict[str, float] = {
        "learning_rate": 3e-4,
        "beta1": 0.9,
        "beta2": 0.999,
    },
) -> None:
    assert isinstance(typed_dict_a, dict)
    assert isinstance(typed_dict_b, dict)
    assert isinstance(standard_dict, dict)
    print("Typed dict A:", typed_dict_a)
    print("Typed dict B:", typed_dict_b)
    print("Standard dict:", standard_dict)


if __name__ == "__main__":
    tyro.cli(main)
