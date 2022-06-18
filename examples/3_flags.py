import dataclasses
from typing import Optional

import dcargs


@dataclasses.dataclass
class Args:
    # Color input.
    red: int
    green: int
    blue: int

    # Boolean values.
    flag: bool
    optional_flag: Optional[bool]
    flag1: bool = False
    flag2: bool = True


if __name__ == "__main__":
    args = dcargs.cli(Args)
    print(args)
    print()
    print(dcargs.to_yaml(args))
