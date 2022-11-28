import enum
from typing import Iterable, Type, TypeVar, Union

from typing_extensions import Literal

T = TypeVar("T", bound=Union[int, str, bool, enum.Enum])


def literal_type_from_choices(choices: Iterable[T]) -> Type[T]:
    """Generate a `typing.Literal[]` type that constrains values to a set of choices.

    .. warning::

        Use of this helper is discouraged because it is compatible with ``pyright`` and
        ``pylance``, but not with ``mypy``. For ``pyright`` support, you may need to enable
        postponed evaluation of annotations (``from __future__ import annotations``).

        At the cost of verbosity, using ``typing.Literal[]`` directly is better supported
        by external tools.

        Alternatively, we can work around this limitation with an ``if TYPE_CHECKING``
        guard:

        .. code-block:: python

            from typing import TYPE_CHECKING

            if TYPE_CHECKING:
                Color = str  # For mypy.
            else:
                Color = literal_type_from_choices(["red", "green", "blue"])

    Using `Literal[...]` directly should generally be preferred, but this helper can be
    used in the rare case that choices are generated dynamically. (for example, the keys
    of a dictionary)
    """
    return Literal.__getitem__(tuple(choices))  # type: ignore
