"""Wrapper type for treating arbitrary annotations as structs.

This is in its own module to avoid the cost of creating a dataclass when it's unused."""

from __future__ import annotations

import dataclasses
from typing import Generic, TypeVar

from typing_extensions import Annotated

from .conf import _confstruct

T = TypeVar("T")


# We skip code generation, since it's slow.
@dataclasses.dataclass(init=False, repr=False, eq=False)
class DummyWrapper(Generic[T]):
    __tyro_dummy_inner__: Annotated[T, _confstruct.arg(name="")]

    def __init__(self, __tyro_dummy_inner__: T) -> None:
        self.__tyro_dummy_inner__ = __tyro_dummy_inner__
