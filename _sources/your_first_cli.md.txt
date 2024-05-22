# Your first CLI

To get started with `tyro`, consider the simple `argparse`-based command-line
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
issues: it requires a significant amount of parsing-specific boilerplate, lacks
type checking and IDE support (consider: jumping to definitions, finding
references, docstrings, refactoring and renaming tools), and becomes difficult
to manage for larger projects.

:func:`tyro.cli()` aims to solve these issues.

**(1) Command-line interfaces from functions.**

We can write the same script as above using `tyro.cli()`:

```python
"""Sum two numbers by calling a function with tyro."""
import tyro

def add(a: int, b: int = 3) -> int:
    return a + b

# Populate the inputs of add(), call it, then return the output.
total = tyro.cli(add)

print(total)
```

Or, more succinctly:

```python
"""Sum two numbers by calling a function with tyro."""
import tyro

def add(a: int, b: int = 3) -> None:
    print(a + b)

tyro.cli(add)  # Returns `None`.
```

**(2) Command-line interfaces from config objects.**

A class in Python can be treated as a function that returns an instance:

```python
"""Sum two numbers by instantiating a dataclass with tyro."""
from dataclasses import dataclass

import tyro

@dataclass
class Args:
    a: int
    b: int = 3

args = tyro.cli(Args)
print(args.a + args.b)
```

Unlike directly using `argparse`, both the function-based and dataclass-based
approaches are compatible with static analysis; tab completion and type checking
will work out-of-the-box.

And that's it! By incorporating more standard type annotations, we can specify a
broad range of more advanced behaviors: nested structures, variable-length
inputs, unions over types, subcommands, and more. Our examples walk through a
selection of these features.
