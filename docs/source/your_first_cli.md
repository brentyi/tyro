# Your first CLI

For getting started with `tyro`, consider the simple `argparse`-based
command-line interface:

```python
"""Sum two numbers from argparse."""

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--a", type=int, required=True)
parser.add_argument("--b", type=int, default=3)
args = parser.parse_args()

print(args.a + args.b)
```

This is dramatically cleaner than manually parsing `sys.argv`, but has several
issues: it lacks type checking and IDE support (consider: jumping to
definitions, finding references, docstrings, refactoring and renaming tools),
requires a significant amount of boilerplate, and generally becomes difficult to
manage as interfaces grow.

The basic feature of :func:`tyro.cli()` is to provide a wrapper for `argparse`
that solves these issues.

We can specify the same logic with a function signature:

```python
"""Sum two numbers by calling a function with tyro."""

import tyro

def main(a: int, b: int = 3) -> None:
    print(a + b)

tyro.cli(main)
```

Particularly when interfaces grow in complexity or require hierarchical
structures, dataclasses can also be helpful:

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

And that's it for the core API! By incorporating more advanced type annotations
from the standard library, we can specify a broad range of more advanced
behaviors: variable-length inputs, unions over types, subcommands, and more. Our
examples walk through a selection of these features.
