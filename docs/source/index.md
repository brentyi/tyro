# tyro

|ruff| |nbsp| |mypy| |nbsp| |pyright| |nbsp| |coverage| |nbsp| |versions|

:func:`tyro.cli()` is a tool for generating CLI interfaces from type-annotated Python.

We can define configurable scripts using functions:

```python
"""A command-line interface defined using a function signature.

Usage: python script_name.py --foo INT [--bar STR]
"""

import tyro

def main(foo: int, bar: str = "default") -> None:
    ...  # Main body of a script.

if __name__ == "__main__":
    # Generate a CLI and call `main` with its two arguments: `foo` and `bar`.
    tyro.cli(main)
```

Or instantiate config objects defined using tools like `dataclasses`, `pydantic`, and `attrs`:

```python
"""A command-line interface defined using a class signature.

Usage: python script_name.py --foo INT [--bar STR]
"""

from dataclasses import dataclass
import tyro

@dataclass
class Config:
    foo: int
    bar: str = "default"

if __name__ == "__main__":
    # Generate a CLI and instantiate `Config` with its two arguments: `foo` and `bar`.
    config = tyro.cli(Config)

    # Rest of script.
    assert isinstance(config, Config)  # Should pass.
```

Other features include helptext generation, nested structures, subcommands, and
shell completion.

#### Why `tyro`?

1. **Define things once.** Standard Python type annotations, docstrings, and
   default values are parsed to automatically generate command-line interfaces
   with informative helptext.

2. **Static types.** Unlike tools dependent on dictionaries, YAML, or dynamic
   namespaces, arguments populated by `tyro` benefit from IDE and language
   server-supported operations — tab completion, rename, jump-to-def,
   docstrings on hover — as well as static checking tools like `pyright` and
   `mypy`.

3. **Modularity.** `tyro` supports hierarchical configuration structures, which
   make it easy to decentralize definitions, defaults, and documentation.

<!-- prettier-ignore-start -->

.. toctree::
   :caption: Getting started
   :hidden:
   :maxdepth: 1
   :titlesonly:

   installation
   your_first_cli
   whats_supported

.. toctree::
   :caption: Examples
   :hidden:
   :titlesonly:

   ./examples/basics.rst
   ./examples/hierarchical_structures.rst
   ./examples/subcommands.rst
   ./examples/overriding_configs.rst
   ./examples/generics.rst
   ./examples/custom_constructors.rst
   ./examples/pytorch_jax.rst


.. toctree::
   :caption: Notes
   :hidden:
   :maxdepth: 5
   :glob:

   goals_and_alternatives
   helptext_generation
   tab_completion


.. toctree::
   :caption: API Reference
   :hidden:
   :maxdepth: 5
   :titlesonly:

   api/tyro/index



.. |mypy| image:: https://github.com/brentyi/tyro/actions/workflows/mypy.yml/badge.svg
   :alt: Mypy status icon
   :target: https://github.com/brentyi/tyro
.. |pyright| image:: https://github.com/brentyi/tyro/actions/workflows/pyright.yml/badge.svg
   :alt: Mypy status icon
   :target: https://github.com/brentyi/tyro
.. |ruff| image:: https://github.com/brentyi/tyro/actions/workflows/ruff.yml/badge.svg
   :alt: Lint status icon
   :target: https://github.com/brentyi/tyro
.. |coverage| image:: https://codecov.io/gh/brentyi/tyro/branch/main/graph/badge.svg
   :alt: Test coverage status icon
   :target: https://codecov.io/gh/brentyi/tyro
.. |downloads| image:: https://pepy.tech/badge/tyro
   :alt: Download count icon
   :target: https://pypi.org/project/tyro/
.. |versions| image:: https://img.shields.io/pypi/pyversions/tyro
   :alt: Version icon
   :target: https://pypi.org/project/tyro/
.. |nbsp| unicode:: 0xA0
   :trim:

<!-- prettier-ignore-end -->
