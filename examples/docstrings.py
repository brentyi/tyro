import dataclasses

import dcargs


@dcargs.parse
@dataclasses.dataclass
class Args:
    # Color input.
    red: int
    green: int
    blue: int

    # Boolean values.
    # These are useful!
    flag: bool
    flag1: bool = False
    flag2: bool = True


print(Args.red)
