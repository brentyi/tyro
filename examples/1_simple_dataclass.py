import dataclasses

import dcargs


@dataclasses.dataclass
class Args:
    """Description.
    This should show up in the helptext!"""

    field1: str  # A string field.
    field2: int  # A numeric field.
    flag: bool = False  # A boolean flag.


if __name__ == "__main__":
    args = dcargs.cli(Args)
    print(args)
    print()
    print(dcargs.to_yaml(args))
