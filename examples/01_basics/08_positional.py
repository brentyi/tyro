"""Positional arguments

Positional-only arguments in functions are converted to positional CLI arguments.

Note: If a double-dash ('--') appears in a command line, everything afterward
will be considered positional.

To accept a variable number of paths without a leading flag, use a positional-only
list parameter. For example, save the following as ``files.py``:

.. code-block:: python

    import pathlib

    import tyro

    def main(files: list[pathlib.Path], /) -> None:
        print(files)

    if __name__ == "__main__":
        tyro.cli(main)

Running ``python files.py ./a ./b`` passes both paths in ``files``. A positional
list accepts zero or more values, so ``python files.py`` passes an empty list.
To require at least one path, use a separate scalar parameter before the list:

.. code-block:: python

    def main(first: pathlib.Path, rest: list[pathlib.Path], /) -> None:
        print([first, *rest])

The ``/`` matters: ``files: list[pathlib.Path]`` without it creates a ``--files``
option. Likewise, ``*files: pathlib.Path`` creates a ``--files`` option rather than
positional CLI arguments.

For more general positional arguments, see :class:`tyro.conf.Positional`.

Usage:

    python 08_positional.py --help
    python 08_positional.py ./a ./b
    python 08_positional.py ./test1 ./test2 --verbose
"""

from __future__ import annotations

import pathlib

import tyro


def main(
    source: pathlib.Path,
    dest: pathlib.Path,
    /,  # Mark the end of positional arguments.
    verbose: bool = False,
) -> None:
    """Command-line interface defined using a function signature. This
    docstring is parsed to generate helptext.

    Args:
        source: Source path.
        dest: Destination path.
        verbose: Explain what is being done.
    """
    print(f"{source=}\n{dest=}\n{verbose=}")


if __name__ == "__main__":
    tyro.cli(main)
