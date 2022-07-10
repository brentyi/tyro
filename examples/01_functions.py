"""In the simplest case, `dcargs.cli()` can be used to run a function with arguments
populated from the CLI.

Usage:
`python ./01_functions.py --help`
`python ./01_functions.py --field1 hello`
`python ./01_functions.py --field1 hello --flag`
"""

import dcargs


def main(
    field1: str,
    field2: int = 3,
    flag: bool = False,
) -> None:
    """Function, whose arguments will be populated from a CLI interface.

    Args:
        field1: A string field.
        field2: A numeric field, with a default value.
        flag: A boolean flag.
    """
    print(field1, field2, flag)


if __name__ == "__main__":
    dcargs.cli(main)
