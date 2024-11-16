from typing import Any


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


class PropagatingMissingType(Singleton):
    pass


class NonpropagatingMissingType(Singleton):
    pass


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

    def main(inner: Dataclass = tyro.constructors.MISSING_NONPROP) -> None:
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

# When total=False in a TypedDict, we exclude fields from the constructor by default.
NOT_REQUIRED_BUT_WE_DONT_KNOW_THE_VALUE = NotRequiredButWeDontKnowTheValueType()


EXCLUDE_FROM_CALL = ExcludeFromCallType()


MISSING_AND_MISSING_NONPROP = (
    MISSING,
    MISSING_NONPROP,
)
"""Singletons that are considered missing values when generating CLI interfaces."""

DEFAULT_SENTINEL_SINGLETONS = MISSING_AND_MISSING_NONPROP + (
    NOT_REQUIRED_BUT_WE_DONT_KNOW_THE_VALUE,
    EXCLUDE_FROM_CALL,
)
