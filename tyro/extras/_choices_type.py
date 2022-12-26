import enum
from typing import Iterable, TypeVar, Union

from typing_extensions import Literal

from .._typing import TypeForm

T = TypeVar("T", bound=Union[int, str, bool, enum.Enum])


def literal_type_from_choices(choices: Iterable[T]) -> TypeForm[T]:
    """Generate a `typing.Literal[]` type that constrains values to a set of choices.

    .. warning::

        Use of this helper is discouraged. It will likely be deprecated.

        The the returned type is understood as an annotation by ``pyright`` and
        ``pylance`` (with ``from __future__ import annotations``), but it relies on
        behavior that isn't defined by the Python language specifications.

        At the cost of verbosity, using ``typing.Literal[]`` directly is better supported
        by tools like ``mypy``.

        Alternatively, we can work around this limitation with an ``if TYPE_CHECKING``
        guard:

        .. code-block:: python

            from typing import TYPE_CHECKING

            if TYPE_CHECKING:
                # Static type seen by mypy, language servers, etc.
                Color = str
            else:
                # Runtime type used by tyro.
                Color = literal_type_from_choices(["red", "green", "blue"])

    Using `Literal[...]` directly should generally be preferred, but this helper can be
    used in the rare case that choices are generated dynamically. (for example, the keys
    of a dictionary)
    """
    return Literal.__getitem__(tuple(choices))  # type: ignore
