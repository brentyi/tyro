import dataclasses
import inspect
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
MISSING_PROP = PropagatingMissingType()
MISSING_NONPROP = NonpropagatingMissingType()

# When total=False in a TypedDict, we exclude fields from the constructor by default.
NOT_REQUIRED_BUT_WE_DONT_KNOW_THE_VALUE = NotRequiredButWeDontKnowTheValueType()


EXCLUDE_FROM_CALL = ExcludeFromCallType()

# Our "public" missing API will always be the propagating missing sentinel.
MISSING: Any = MISSING_PROP
"""Sentinel value to mark fields as missing. Can be used to mark fields passed
in via `default=` for `tyro.cli()` as required."""


MISSING_SINGLETONS = [
    dataclasses.MISSING,
    MISSING_PROP,
    MISSING_NONPROP,
    inspect.Parameter.empty,
]
try:
    # Undocumented feature: support omegaconf dataclasses out of the box.
    import omegaconf

    MISSING_SINGLETONS.append(omegaconf.MISSING)
except ImportError:
    pass

DEFAULT_SENTINEL_SINGLETONS = MISSING_SINGLETONS + [
    NOT_REQUIRED_BUT_WE_DONT_KNOW_THE_VALUE,
    EXCLUDE_FROM_CALL,
]
