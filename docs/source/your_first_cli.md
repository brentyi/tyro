# Your First CLI

To get started with `tyro`, let's compare it with a traditional `argparse`-based command-line
interface:

```python
"""Sum two numbers from argparse."""
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--a", type=int, required=True)
parser.add_argument("--b", type=int, default=3)
args = parser.parse_args()

total = args.a + args.b

print(total)
```

This is dramatically cleaner than manually parsing `sys.argv`, but has several
issues:

- It requires significant parsing-specific boilerplate.
- It lacks type checking and IDE support (no jumping to definitions, finding
  references, docstrings, refactoring or renaming tools).
- It becomes difficult to manage for larger projects with many parameters.
- It doesn't automatically generate comprehensive help text.

:func:`tyro.cli()` aims to solve these issues by building CLIs directly from type annotations.

## Command-line interfaces from functions

We can write the same script as above using `tyro.cli()`:

```python
"""Sum two numbers by calling a function with tyro."""
import tyro

def add(a: int, b: int = 3) -> int:
    """Add two numbers together.

    Args:
        a: First number to add.
        b: Second number to add. Defaults to 3.
    """
    return a + b

# Populate the inputs of add(), call it, then return the output.
total = tyro.cli(add)

print(total)
```

Using this script from the command line would look like:

```
$ python script.py --a 5
8

$ python script.py --a 5 --b 7
12

$ python script.py --help
usage: script.py [-h] --a INT [--b INT]

Add two numbers together.

╭─ options ───────────────────────────────────────────────────────────╮
│ -h, --help        show this help message and exit                   │
│ --a INT           First number to add. (required)                   │
│ --b INT           Second number to add. Defaults to 3. (default: 3) │
╰─────────────────────────────────────────────────────────────────────╯
```

A more succinct version that combines the function call with printing:

```python
"""Sum two numbers by calling a function with tyro."""
import tyro

def add(a: int, b: int = 3) -> None:
    """Add two numbers together and print the result."""
    print(a + b)

tyro.cli(add)  # Parses arguments, calls add(), and returns None.
```

## Command-line interfaces from config objects

A class in Python can be treated as a function that returns an instance. This is
particularly useful for more complex configurations:

```python
"""Sum two numbers by instantiating a dataclass with tyro."""
from dataclasses import dataclass

import tyro

@dataclass
class Args:
    """Configuration for adding two numbers."""

    a: int  # First number to add
    b: int = 3  # Second number to add (default: 3)

args = tyro.cli(Args)
print(args.a + args.b)
```

From the command line, this would look identical to the function example:

```
$ python script.py --a 5
8

$ python script.py --help
usage: script.py [-h] --a INT [--b INT]

Configuration for adding two numbers.

╭─ options ────────────────────────────────────────────────────────╮
│ -h, --help        show this help message and exit                │
│ --a INT           First number to add (required)                 │
│ --b INT           Second number to add (default: 3) (default: 3) │
╰──────────────────────────────────────────────────────────────────╯
```

## Benefits over argparse

Unlike directly using `argparse`, both the function-based and dataclass-based
approaches provide:

1. **Static type checking** - Parameters have real types that can be checked.
2. **IDE support** - Jump to definitions, find references, see docstrings, and use refactoring tools.
3. **Automatic helptext** - Generated from docstrings and comments.
4. **Less boilerplate** - No need to manually define every argument.
5. **Hierarchical configuration** - Easily nest parameters in complex structures.

By incorporating standard type annotations, tyro can handle a broad range of advanced behaviors:
nested structures, variable-length inputs, unions over types, subcommands, and more.
Our examples walk through these features in detail.
