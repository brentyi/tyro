import dataclasses

import dcargs


@dataclasses.dataclass
class Args:
    field1: str  # A string field.
    field2: int  # A numeric field.


if __name__ == "__main__":
    args = dcargs.parse(Args)
    print(args)
