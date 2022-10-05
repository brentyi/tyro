# tyro

|build| |nbsp| |mypy| |nbsp| |lint| |nbsp| |coverage| |nbsp| |versions|

:code:`tyro` is a library for building CLI interfaces, configuration objects,
and configuration _systems_ with modern, type-annotated Python.

Our core interface consists of just one function, :func:`tyro.cli()`, which
translates Python callables and types into fully-featured argument parsers and
configuration objects.

To get started, we recommend browsing the examples to the left.

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

3. **Automatic helptext generation.**

   `tyro` parses docstrings, types, and defaults to generate carefully formatted
   helptext. Longer messages are organized into responsive multi-column layouts.

4. **Modularity.**

   `tyro` supports hierarchically nested configuration structures, which make it
   easy to distribute definitions, defaults, and documentation of configurable
   fields across modules or source files.

5. **Tab completion.**

   By extending [shtab](https://github.com/iterative/shtab), `tyro`
   automatically generates tab completion scripts for bash, zsh, and tcsh!

### In the wild

`tyro` is still a new library, but being stress tested in several projects!

- [nerfstudio](https://github.com/nerfstudio-project/nerfstudio/) uses `tyro`
  both to build compact command-line utilities and for YAML-free experiment
  configuration.
- [obj2mjcf](https://github.com/kevinzakka/obj2mjcf) uses `tyro` to build a CLI
  for processing composite Wavefront OBJ files for Mujoco.
- [tensorf-jax](https://github.com/brentyi/tensorf-jax/) implements
  [Tensorial Radiance Fields](https://apchenstu.github.io/TensoRF/) in JAX, with
  `tyro` for configuration.

<!-- prettier-ignore-start -->

.. toctree::
   :caption: Getting started
   :maxdepth: 1
   :hidden:
   :titlesonly:

   installation
   your_first_cli

.. toctree::
   :caption: Notes
   :maxdepth: 5
   :hidden:
   :glob:

   helptext_generation
   tab_completion
   building_configuration_systems
   goals_and_alternatives

.. toctree::
   :caption: Examples
   :maxdepth: 1
   :hidden:
   :titlesonly:
   :glob:

   examples/*

.. toctree::
   :caption: API Reference
   :maxdepth: 5
   :hidden:
   :titlesonly:

   api/tyro/index



.. |build| image:: https://github.com/brentyi/tyro/workflows/build/badge.svg
   :alt: Build status icon
   :target: https://github.com/brentyi/tyro
.. |mypy| image:: https://github.com/brentyi/tyro/workflows/mypy/badge.svg?branch=master
   :alt: Mypy status icon
   :target: https://github.com/brentyi/tyro
.. |lint| image:: https://github.com/brentyi/tyro/workflows/lint/badge.svg
   :alt: Lint status icon
   :target: https://github.com/brentyi/tyro
.. |coverage| image:: https://codecov.io/gh/brentyi/tyro/branch/master/graph/badge.svg
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