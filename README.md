<br />
<p align="center">
    <!--
    Note that this README will be used for both GitHub and PyPI.
    We therefore:
    - Keep all image URLs absolute.
    - In the GitHub action we use for publishing, strip some HTML tags that aren't supported by PyPI.
    -->
    <!-- pypi-strip -->
    <picture>
        <source media="(prefers-color-scheme: dark)" srcset="https://brentyi.github.io/tyro/_static/logo-dark.svg" />
    <!-- /pypi-strip -->
        <img alt="tyro logo" src="https://brentyi.github.io/tyro/_static/logo-light.svg" width="200px" />
    <!-- pypi-strip -->
    </picture>
    <!-- /pypi-strip -->

</p>

<p align="center">
    <em><a href="https://brentyi.github.io/tyro">Documentation</a></em>
    &nbsp;&nbsp;&bull;&nbsp;&nbsp;
    <em><code>pip install tyro</code></em>
</p>

<p align="center">
    <img alt="build" src="https://github.com/brentyi/tyro/workflows/build/badge.svg" />
    <img alt="mypy" src="https://github.com/brentyi/tyro/workflows/mypy/badge.svg?branch=main" />
    <img alt="lint" src="https://github.com/brentyi/tyro/workflows/lint/badge.svg" />
    <a href="https://codecov.io/gh/brentyi/tyro">
        <img alt="codecov" src="https://codecov.io/gh/brentyi/tyro/branch/main/graph/badge.svg" />
    </a>
    <a href="https://pypi.org/project/tyro/">
        <img alt="codecov" src="https://img.shields.io/pypi/pyversions/tyro" />
    </a>
</p>

<br />

<strong><code>tyro</code></strong> is a tool for generating command-line
interfaces and configuration objects from type-annotated Python. We:

- Introduce a single-function core API, `tyro.cli()`, which is minimal enough to
  use in throwaway scripts but flexible enough to be hardened in larger
  projects.
- Support a broad range of Python type constructs, including basics (`int`,
  `str`, `bool`, `float`, `pathlib.Path`, ...), both fixed- and variable-length
  containers (`list[T]`, `tuple[T1, T2, ...]`, `set[T]`, `dict[K, V]`), unions
  (`X | Y`, `Union[X, Y]`), literals (`Literal`), and generics (`TypeVar`).
- Understand hierarchy, nesting, and tools you may already use, like
  `dataclasses`, `pydantic`, and `attrs`.
- Generate helptext automatically from defaults, annotations, and docstrings.
- Provide flexible support for subcommands, as well as choosing between and
  overriding values in configuration objects.
- Enable tab completion in both your IDE and terminal.
- Expose fine-grained configuration via PEP 529 runtime annotations
  (`tyro.conf.*`).

`tyro`'s use cases overlaps significantly with many other tools. The differences
are a result of several API goals:

- Focusing on a single, uninvasive function.
- Prioritizing compatibility with language servers and type checkers.
- Avoiding assumptions on serialization formats (like YAML or JSON) for
  configuration objects.

### Brief walkthrough

To summarize how `tyro.cli()` can be used, let's consider a script based on
`argparse`. We define two inputs and print the sum:

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

This pattern is dramatically cleaner than manually parsing `sys.argv`, but has
several issues: it requires a significant amount of parsing-specific
boilerplate, lacks type checking and IDE support (consider: jumping to
definitions, finding references, docstrings, refactoring and renaming tools),
and becomes difficult to manage for larger projects.

The basic goal of `tyro.cli()` is to provide a wrapper for `argparse` that
solves these issues.

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

A class in Python can be treated as a function that returns an instance. This
makes it easy to populate explicit configuration structures:

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

### In the wild

`tyro` is still a new library, but being stress tested in several projects!

- [nerfstudio-project/nerfstudio](https://github.com/nerfstudio-project/nerfstudio/)
  provides a set of tools for end-to-end training, testing, and rendering of
  neural radiance fields.
- [Sea-Snell/JAXSeq](https://github.com/Sea-Snell/JAXSeq/) is a library for
  distributed training of large language models in JAX.
- [kevinzakka/obj2mjcf](https://github.com/kevinzakka/obj2mjcf) is an interface
  for processing composite Wavefront OBJ files for Mujoco.
- [blurgyy/jaxngp](https://github.com/blurgyy/jaxngp) is a CUDA-accelerated
  implementation of [instant-ngp](https://nvlabs.github.io/instant-ngp/),
  implemented in JAX.
- [NVIDIAGameWorks/kaolin-wisp](https://github.com/NVIDIAGameWorks/kaolin-wisp)
  combines `tyro` with
  [`hydra-zen`](https://github.com/mit-ll-responsible-ai/hydra-zen) for neural
  fields in PyTorch.
- [openrlbenchmark/openrlbenchmark](https://github.com/openrlbenchmark/openrlbenchmark)
  is a collection of tracked experiments for reinforcement learning.
