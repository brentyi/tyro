"""Wrapper type for treating arbitrary annotations as structs.

This is in its own module to avoid the cost of creating a dataclass when it's unused."""

from __future__ import annotations

import dataclasses
from typing import Generic, TypeVar

from typing_extensions import Annotated

from .conf import _confstruct

T = TypeVar("T")


@dataclasses.dataclass(frozen=True)
class DummyWrapper(Generic[T]):
    __tyro_dummy_inner__: Annotated[T, _confstruct.arg(name="")]
