"""Lightweight stand-in for `dataclasses.dataclass`.

Each `@dataclass` decorator generates and compiles code at import time. This typically
costs around a millisecond per class, which adds up to a significant portion of tyro's
total runtime. Internal classes inherit from `Record` and implement their `__init__()`
methods manually instead: this is stored as bytecode and is basically free.

Classes in our public API are still dataclasses.
"""

from __future__ import annotations

from typing import Any, ClassVar, TypeVar

_RecordT = TypeVar("_RecordT", bound="Record")


class Record:
    """Base class for records. Equality is identity-based by default."""

    _fields: ClassVar[tuple[str, ...]] = ()

    def __repr__(self) -> str:
        fields = ", ".join(f"{k}={getattr(self, k)!r}" for k in self._fields)
        return f"{type(self).__qualname__}({fields})"

    def replace(self: _RecordT, **changes: Any) -> _RecordT:
        """Make a shallow copy with some attributes changed."""
        out = object.__new__(type(self))
        out.__dict__.update(
            {k: v for k, v in self.__dict__.items() if k in self._fields}
        )
        out.__dict__.update(changes)
        return out


class ValueRecord(Record):
    """Record with value-based equality and hashing, like a frozen dataclass."""

    def _astuple(self) -> tuple[Any, ...]:
        return tuple(getattr(self, k) for k in self._fields)

    def __eq__(self, other: object) -> bool:
        if other.__class__ is not self.__class__:
            return NotImplemented
        return self._astuple() == other._astuple()  # type: ignore

    def __hash__(self) -> int:
        return hash(self._astuple())
