import enum
from typing import Iterable, Type, TypeVar, Union

from typing_extensions import Literal

T = TypeVar("T", bound=Union[int, str, bool, enum.Enum])


def literal_type_from_choices(choices: Iterable[T]) -> Type[T]:
    """Generate a typing.Literal[] type that constrains values to a set of choices.

    Using Literal[...] directly should generally be preferred, but this helper can be
    used in the rare case that choices are generated dynamically. (for example, the keys
    of a dictionary)

    Using the returned type as an annotation currently breaks for mypy, but is
    understood by Pyright."""
    return Literal.__getitem__(tuple(choices))  # type: ignore
