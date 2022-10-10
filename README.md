<br />
<p align="center">
    <!-- Note that image URLs should all be absolute; this README will be used for both GitHub and PyPI. -->
    <picture>
        <source media="(prefers-color-scheme: dark)" srcset="https://brentyi.github.io/tyro/_static/logo-dark.svg">
    <img alt="tyro logo" src="https://brentyi.github.io/tyro/_static/logo-light.svg" width="200px">
</picture>

<p align="center">
    <em><a href="https://brentyi.github.io/tyro">Documentation</a></em>
    &nbsp;&nbsp;&bull;&nbsp;&nbsp;
    <em><code>pip install tyro</code></em>
</p>

<p align="center">
    <img alt="build" src="https://github.com/brentyi/tyro/workflows/build/badge.svg" />
    <img alt="mypy" src="https://github.com/brentyi/tyro/workflows/mypy/badge.svg?branch=master" />
    <img alt="lint" src="https://github.com/brentyi/tyro/workflows/lint/badge.svg" />
    <a href="https://codecov.io/gh/brentyi/tyro">
        <img alt="codecov" src="https://codecov.io/gh/brentyi/tyro/branch/master/graph/badge.svg" />
    </a>
    <a href="https://pypi.org/project/tyro/">
        <img alt="codecov" src="https://img.shields.io/pypi/pyversions/tyro" />
    </a>
</p>

<br />

<strong><code>tyro</code></strong> is a library for building CLI interfaces,
configuration objects, and configuration systems with modern, type-annotated
Python.

Our core interface consists of just one function, `tyro.cli()`, that translates
Python callables and types into fully-featured argument parsers and
configuration objects.

To get started, we recommend visiting the examples in our
[documentation](https://brentyi.github.io/tyro).

### Why `tyro`?

1. **Strong typing.**

   Unlike tools dependent on dictionaries, YAML, or dynamic namespaces,
   arguments populated by `tyro` benefit from IDE and language server-supported
   operations — think tab completion, rename, jump-to-def, docstrings on hover —
   as well as static checking tools like `pyright` and `mypy`.

2. **Minimal overhead.**

   Standard Python type annotations, docstrings, and default values are parsed
   to automatically generate command-line interfaces with informative helptext.

   If you're familiar with type annotations and docstrings in Python, you
   already know how to use `tyro`! If you're not, learning to use `tyro` reduces
   to learning to write modern Python.

   Hate `tyro`? Just remove one line of code, and you're left with beautiful,
   type-annotated, and documented vanilla Python that can be used with a range
   of other configuration libraries.

3. **Modularity.**

   `tyro` supports hierarchical configuration structures, which make it easy to
   distribute definitions, defaults, and documentation of configurable fields
   across modules or source files.

4. **Tab completion.**

   By extending [shtab](https://github.com/iterative/shtab), `tyro`
   automatically generates tab completion scripts for bash, zsh, and tcsh.

### A minimal example

As a replacement for `argparse`:

<table align="">
<tr>
    <td><strong>with argparse</strong></td>
    <td><strong>with tyro</strong></td>
</tr>
<tr>
<td>

```python
"""Sum two numbers from argparse."""

import argparse
parser = argparse.ArgumentParser()
parser.add_argument(
    "--a",
    type=int,
    required=True,
)
parser.add_argument(
    "--b",
    type=int,
    default=3,
)
args = parser.parse_args()

print(args.a + args.b)
```

</td>
<td>

```python
"""Sum two numbers by calling a
function with tyro."""

import tyro

def main(a: int, b: int = 3) -> None:
    print(a + b)

tyro.cli(main)
```

---

```python
"""Sum two numbers by instantiating
a dataclass with tyro."""

from dataclasses import dataclass

import tyro

@dataclass
class Args:
    a: int
    b: int = 3

args = tyro.cli(Args)
print(args.a + args.b)
```

</td>
</tr>
</table>

For more examples, see our [documentation](https://brentyi.github.io/tyro).

### In the wild

`tyro` is still a new library, but being stress tested in several projects!

- [nerfstudio-project/nerfstudio](https://github.com/nerfstudio-project/nerfstudio/)
  provides a set of tools for end-to-end training, testing, and rendering of
  neural radiance fields.
- [Sea-Snell/JAXSeq](https://github.com/Sea-Snell/JAXSeq/) is a library for
  distributed training of large language models in JAX.
- [kevinzakka/obj2mjcf](https://github.com/kevinzakka/obj2mjcf) is an interface
  for processing composite Wavefront OBJ files for Mujoco.
- [brentyi/tensorf-jax](https://github.com/brentyi/tensorf-jax/) is an
  unofficial implementation of
  [Tensorial Radiance Fields](https://apchenstu.github.io/TensoRF/) in JAX.
