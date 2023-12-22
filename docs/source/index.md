# tyro

|build| |nbsp| |ruff| |nbsp| |mypy| |nbsp| |pyright| |nbsp| |coverage| |nbsp| |versions|

:code:`tyro` is a tool for generating command-line interfaces and configuration
objects in Python.

Our core API, `tyro.cli()`,

- **Generates CLI interfaces** from a comprehensive set of Python type
  constructs.
- **Populates helptext automatically** from defaults, annotations, and
  docstrings.
- **Understands nesting** of `dataclasses`, `pydantic`, and `attrs` structures.
- **Prioritizes static analysis** for type checking and autocompletion with
  tools like
  [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance),
  [Pyright](https://github.com/microsoft/pyright), and
  [mypy](https://github.com/python/mypy).

For advanced users, it also supports:

- **Subcommands**, as well as choosing between and overriding values in
  configuration objects.
- **Completion script generation** for `bash`, `zsh`, and `tcsh`.
- **Fine-grained configuration** via PEP 529 runtime annotations
  (`tyro.conf.*`).

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

   `tyro` works seamlessly with tools you already use: examples are included for
   [dataclasses](https://docs.python.org/3/library/dataclasses.html),
   [attrs](https://www.attrs.org/),
   [pydantic](https://pydantic-docs.helpmanual.io/),
   [flax.linen](https://flax.readthedocs.io/en/latest/api_reference/flax.linen.html),
   and more.

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

<!-- prettier-ignore-start -->

.. toctree::
   :caption: Getting started
   :hidden:
   :maxdepth: 1
   :titlesonly:

   installation
   your_first_cli

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
   :caption: Notes
   :hidden:
   :maxdepth: 5
   :glob:

   goals_and_alternatives
   helptext_generation
   tab_completion
   building_configuration_systems


.. toctree::
   :caption: API Reference
   :hidden:
   :maxdepth: 5
   :titlesonly:

   api/tyro/index



.. |build| image:: https://github.com/brentyi/tyro/actions/workflows/build.yml/badge.svg
   :alt: Build status icon
   :target: https://github.com/brentyi/tyro
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
