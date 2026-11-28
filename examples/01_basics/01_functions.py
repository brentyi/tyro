"""Functions

In the simplest case, :func:`tyro.cli()` can be used to run a function with
arguments populated from the CLI.

To supply default values for a function's parameters at runtime without
changing its signature, wrap it with :func:`functools.partial`:

.. code-block:: python

    from functools import partial

    import tyro

    def greet(name: str) -> None:
        print(f"Hello, {name}")

    if __name__ == "__main__":
        default_kwargs = {"name": "Alice"}
        tyro.cli(partial(greet, **default_kwargs))

Running the script with no flags prints ``Hello, Alice``, while passing
``--name Bob`` overrides the partial default and prints ``Hello, Bob``.

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
