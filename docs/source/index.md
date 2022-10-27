# tyro

|build| |nbsp| |mypy| |nbsp| |lint| |nbsp| |coverage| |nbsp| |versions|

:code:`tyro` is a library for building CLI interfaces and configuration objects
with type-annotated Python.

Our core interface consists of one function, :func:`tyro.cli()`, that generates
argument parsers from Python callables and types.

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

3. **Modularity.**

   `tyro` supports hierarchical configuration structures, which make it easy to
   distribute definitions, defaults, and documentation of configurable fields
   across modules or source files.

4. **Tab completion.**

   By extending [shtab](https://github.com/iterative/shtab), `tyro`
   automatically generates tab completion scripts for bash, zsh, and tcsh.

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

<!-- prettier-ignore-start -->

.. toctree::
   :caption: Getting started
   :hidden:
   :maxdepth: 1
   :titlesonly:

   installation
   your_first_cli

.. toctree::
   :caption: Notes
   :hidden:
   :maxdepth: 5
   :glob:

   goals_and_alternatives
   helptext_generation
   tab_completion
   building_configuration_systems

.. toctree::
   :caption: Basics
   :hidden:
   :maxdepth: 1
   :titlesonly:
   :glob:

   examples/01_basics/*


.. toctree::
   :caption: Hierarchies
   :hidden:
   :maxdepth: 1
   :titlesonly:
   :glob:

   examples/02_nesting/*


.. toctree::
   :caption: Config Management
   :hidden:
   :maxdepth: 1
   :titlesonly:
   :glob:

   examples/03_config_systems/*


.. toctree::
   :caption: Additional Features
   :hidden:
   :maxdepth: 1
   :titlesonly:
   :glob:

   examples/04_additional/*


.. toctree::
   :caption: API Reference
   :hidden:
   :maxdepth: 5
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
