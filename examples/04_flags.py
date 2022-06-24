"""Example of how booleans are handled and automatically converted to flags."""

import dataclasses
from typing import Optional

import dcargs


@dataclasses.dataclass
class Args:
    # Boolean. This expects an explicit "True" or "False".
    boolean: bool

    # Optional boolean. Same as above, but can be omitted.
    optional_boolean: Optional[bool]

    # Pass --flag-a in to set this value to True.
    flag_a: bool = False

    # Pass --no-flag-b in to set this value to False.
    flag_b: bool = True


if __name__ == "__main__":
    args = dcargs.cli(Args)
    print(args)
    print()
    print(dcargs.to_yaml(args))
