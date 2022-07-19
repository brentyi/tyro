9. Subparsers
==========================================

Unions over nested types (classes or dataclasses) are populated using subparsers.




Example
------------------------------------------



.. code-block:: python
       :linenos:

       from __future__ import annotations
       
       import dataclasses
       from typing import Union
       
       import dcargs
       
       
       @dataclasses.dataclass(frozen=True)
       class Checkout:
           """Checkout a branch."""
       
           branch: str
       
       
       @dataclasses.dataclass(frozen=True)
       class Commit:
           """Commit changes."""
       
           message: str
           all: bool = False
       
       
       def main(cmd: Union[Checkout, Commit]) -> None:
           print(cmd)
       
       
       if __name__ == "__main__":
           dcargs.cli(main)



Usage
------------------------------------------

.. command-output:: python ../../examples/09_subparsers.py --help

.. command-output:: python ../../examples/09_subparsers.py commit --help

.. command-output:: python ../../examples/09_subparsers.py commit --cmd.message hello --cmd.all

.. command-output:: python ../../examples/09_subparsers.py checkout --help

.. command-output:: python ../../examples/09_subparsers.py checkout --cmd.branch main
