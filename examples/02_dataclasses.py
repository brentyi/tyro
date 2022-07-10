"""Common pattern: use `dcargs.cli()` to instantiate a dataclass.

Usage:
`python ./02_dataclasses.py --help`
`python ./02_dataclasses.py --field1 hello`
`python ./02_dataclasses.py --field1 hello --flag`
"""

import dataclasses

import dcargs


@dataclasses.dataclass
class Args:
    """Description.
    This should show up in the helptext!"""

    field1: str  # A string field.
    field2: int = 3  # A numeric field, with a default value.
    flag: bool = False  # A boolean flag.


if __name__ == "__main__":
    args = dcargs.cli(Args)
    print(args)
