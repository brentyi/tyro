"""Instantiating Classes

In addition to functions and dataclasses, we can also generate CLIs from the
constructors of standard Python classes.

Usage:

    python ./13_classes.py --help
    python ./13_classes.py --field1 hello --field2 7
"""

import tyro


class Args:
    def __init__(
        self,
        field1: str,
        field2: int,
        flag: bool = False,
    ):
        """Arguments.

        Args:
            field1: A string field.
            field2: A numeric field.
            flag: A boolean flag.
        """
        self.data = [field1, field2, flag]


if __name__ == "__main__":
    args = tyro.cli(Args)
    print(args.data)
