import enum
from typing import Iterable, Literal, TypeVar, Union

from .._typing import TypeForm

T = TypeVar("T", bound=Union[int, str, bool, enum.Enum])


def literal_type_from_choices(choices: Iterable[T]) -> TypeForm[T]:
    """Generate a :py:data:`typing.Literal` type that constrains values to a set of choices.

    Using ``Literal[...]`` directly should generally be preferred, but this function can be
    helpful when choices are generated dynamically.

    .. warning::

        The type returned by this function can be safely used as an input to
        :func:`tyro.cli()`, but for static analysis when used for annotations we
        recommend applying a `TYPE_CHECKING` guard:

        .. code-block:: python

            from typing import TYPE_CHECKING

            if TYPE_CHECKING:
                # Static type seen by language servers, type checkers, etc.
                Color = str
            else:
                # Runtime type used by tyro.
                Color = literal_type_from_choices(["red", "green", "blue"])

    Args:
        choices: Options to choose from.

    Returns:
        A type that can be passed to :func:`tyro.cli()`.
    """
    return Literal[tuple(choices)]  # type: ignore
