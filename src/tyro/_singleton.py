import sys
from typing import Any

if sys.version_info >= (3, 11):
    SubclassableAny = Any
else:  # pragma: no cover
    from typing_extensions import Any as SubclassableAny


class Singleton:
    # Singleton pattern.
    # https://www.python.org/download/releases/2.2/descrintro/#__new__
    def __new__(cls, *args, **kwds):
        it = cls.__dict__.get("__it__")
        if it is not None:
            return it
        cls.__it__ = it = object.__new__(cls)
        it.init(*args, **kwds)
        return it

    def init(self, *args, **kwds):
        pass


# We subclass `Any` to prevent typeguard from failing for MISSING types.
#
# https://github.com/agronholm/typeguard/blob/dd98a9a0ff050166716120cc8614fa90d710a879/src/typeguard/_checkers.py#L933-L935


class PropagatingMissingType(Singleton, SubclassableAny):
    """Type for the :data:`tyro.MISSING` singleton."""

    def __repr__(self) -> str:
        return "tyro.MISSING"


class NonpropagatingMissingType(Singleton, SubclassableAny):
    """Type for the :data:`tyro.MISSING_NONPROP` singleton."""

    def __repr__(self) -> str:
        return "tyro.MISSING_NONPROP"


class ExcludeFromCallType(Singleton):
    pass


class NotRequiredButWeDontKnowTheValueType(Singleton):
    pass


# We have two types of missing sentinels: a propagating missing value, which when set as
# a default will set all child values of nested structures as missing as well, and a
# nonpropagating missing sentinel, which does not override child defaults.
MISSING: Any = PropagatingMissingType()
"""Sentinel value to mark default values as missing. Can be used to mark fields
passed in via `default=` for `tyro.cli()` as required.

When used, the 'missing' semantics propagate to children. For example, if we write:

.. code-block:: python

    def main(inner: Dataclass = tyro.MISSING) -> None:
        ...

    tyro.cli(main)

then all fields belonging to ``Dataclass`` will be marked as missing, even if a
default exists in the dataclass definition.
"""
MISSING_NONPROP: Any = NonpropagatingMissingType()
"""Non-propagating version of :data:`tyro.MISSING`.

When used, the 'missing' semantics do not propagate to children. For example:

.. code-block:: python

    def main(inner: Dataclass = tyro.MISSING_NONPROP) -> None:
        ...

    tyro.cli(main)

is equivalent to:

.. code-block:: python

    def main(inner: Dataclass) -> None:
        ...

    tyro.cli(main)

where default values for fields belonging to ``Dataclass`` will be taken from
the dataclass definition.
"""


MISSING_AND_MISSING_NONPROP = (MISSING, MISSING_NONPROP)
"""Singletons that are considered missing values when generating CLI interfaces."""

EXCLUDE_FROM_CALL = ExcludeFromCallType()
"""Singleton indicating that an argument should not be passed into a field
constructor. This is used for :py:class:`typing.TypedDict`."""

DEFAULT_SENTINEL_SINGLETONS = MISSING_AND_MISSING_NONPROP + (EXCLUDE_FROM_CALL,)
"""Singletons that are used as default sentinels when generating CLI interfaces."""
