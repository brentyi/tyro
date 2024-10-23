from dataclasses import dataclass
from typing import Literal

import tyro


@dataclass(frozen=True)
class Container[T]:
    a: T


tyro.cli(Container[Container[bool] | Container[Literal["1", "2"]]])
