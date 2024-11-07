"""Functions

In the simplest case, :func:`tyro.cli()` can be used to run a function with
arguments populated from the CLI.

Usage:

    # We can use ``--help`` to show the help message, or ``--field1`` and
    # ``--field2`` to set the arguments:
    python ./01_functions.py --help
    python ./01_functions.py --field1 hello
    python ./01_functions.py --field1 hello --field2 10

"""

import tyro


def main(field1: str, field2: int = 3) -> None:
    """Function, whose arguments will be populated from a CLI interface.

    Args:
        field1: A string field.
        field2: A numeric field, with a default value.
    """
    print(field1, field2)


if __name__ == "__main__":
    tyro.cli(main)
