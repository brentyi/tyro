"""Dictionaries and TypedDict

Dictionary inputs can be specified using either a standard ``dict[K, V]``
annotation, or a :py:class:`TypedDict` subclass.

For configuring :py:class:`TypedDict`, we also support :code:`total={True/False}`,
:py:data:`typing.Required`, and :py:data:`typing.NotRequired`. See the `Python docs <https://docs.python.org/3/library/typing.html#typing.TypedDict>`_ for all :py:class:`TypedDict` features.

Usage:

    python ./04_dictionaries.py --help
    python ./04_dictionaries.py --typed-dict-a.learning-rate 3e-4 --typed-dict-b.betas 0.9 0.999
    python ./04_dictionaries.py --typed-dict-b.betas 0.9 0.999
"""

from typing import TypedDict

from typing_extensions import NotRequired

import tyro


class DictionarySchemaA(
    TypedDict,
    # Setting `total=False` specifies that not all keys need to exist.
    total=False,
):
    learning_rate: float
    betas: tuple[float, float]


class DictionarySchemaB(TypedDict):
    learning_rate: NotRequired[float]
    """NotRequired[] specifies that a particular key doesn't need to exist."""
    betas: tuple[float, float]


def main(
    typed_dict_a: DictionarySchemaA,
    typed_dict_b: DictionarySchemaB,
    standard_dict: dict[str, float] = {
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
