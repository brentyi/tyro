1. Functions
==========================================

In the simplest case, `dcargs.cli()` can be used to run a function with arguments
populated from the CLI.




Example
------------------------------------------



.. code-block:: python
       :linenos:

       import dcargs
       
       
       def main(
           field1: str,
           field2: int = 3,
       ) -> None:
           """Function, whose arguments will be populated from a CLI interface.
       
           Args:
               field1: A string field.
               field2: A numeric field, with a default value.
           """
           print(field1, field2)
       
       
       if __name__ == "__main__":
           dcargs.cli(main)



Usage
------------------------------------------

.. command-output:: python ../../examples/01_functions.py --help

.. command-output:: python ../../examples/01_functions.py --field1 hello

.. command-output:: python ../../examples/01_functions.py --field1 hello --field2 10
