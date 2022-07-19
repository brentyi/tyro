dcargs
==========================================

|build| |nbsp| |mypy| |nbsp| |lint| |nbsp| |coverage| |nbsp| |versions|

:code:`dcargs` is a library for typed CLI interfaces and configuration objects.

Our core interface, :func:`dcargs.cli`, generates argument parsers from
type-annotated callables. In the simplest case, this can be used as a drop-in
replacement for :code:`argparse`:


.. code:: python

      # With argparse.

      import argparse

      parser = argparse.ArgumentParser()
      parser.add_argument("--a", type=int, required=True)
      parser.add_argument("--b", type=int, default=3)
      args = parser.parse_args()

      print(args.a + args.b)


.. code:: python

      # With dcargs.

      import dcargs

      def main(a: int, b: int = 3) -> None:
          print(a + b)

      dcargs.cli(main)



The broader goal is also a replacement for tools like :code:`hydra`,
:code:`gin-config`, and :code:`ml_collections` that's:

- **Low effort.** Standard Python type annotations, docstrings, and default
  values are parsed to automatically generate command-line interfaces with
  informative helptext.

- **Expressive.** :func:`dcargs.cli` understands functions, classes,
  dataclasses, and *nested* classes and dataclasses, as well as frequently used
  annotations like unions, literals, and collections, which can be composed into
  hierarchical configuration objects built on standard Python features.

- **Typed.** Unlike dynamic configuration namespaces produced by libraries like
  :code:`argparse`, :code:`YACS`, :code:`abseil`, :code:`hydra`, or
  :code:`ml_collections`, typed outputs mean that IDE-assisted autocomplete,
  rename, refactor, and go-to-definition operations work out-of-the-box, as well
  as static checking tools like :code:`mypy` and :code:`pyright`.

- **Modular.** Most approaches to configuration objects require a centralized
  definition of all configurable fields. Hierarchically nesting configuration
  structures, however, makes it easy to distribute definitions, defaults, and
  documentation of configurable fields across modules or source files. A model
  configuration dataclass, for example, can be co-located in its entirety with
  the model implementation and dropped into any experiment configuration with an
  import — this eliminates redundancy and makes entire modules easy to port
  across codebases.


.. toctree::
   :caption: Examples
   :maxdepth: 5
   :titlesonly:
   :glob:

   example_*


.. toctree::
   :caption: Notes
   :maxdepth: 5
   :titlesonly:
   :glob:

   serialization
   alternatives


.. toctree::
   :caption: API Reference
   :maxdepth: 5
   :titlesonly:

   api/dcargs/index



.. |build| image:: https://github.com/brentyi/dcargs/workflows/build/badge.svg
   :alt: Build status icon
   :target: https://github.com/brentyi/dcargs
.. |mypy| image:: https://github.com/brentyi/dcargs/workflows/mypy/badge.svg?branch=master
   :alt: Mypy status icon
   :target: https://github.com/brentyi/dcargs
.. |lint| image:: https://github.com/brentyi/dcargs/workflows/lint/badge.svg
   :alt: Lint status icon
   :target: https://github.com/brentyi/dcargs
.. |coverage| image:: https://codecov.io/gh/brentyi/dcargs/branch/master/graph/badge.svg
   :alt: Test coverage status icon
   :target: https://codecov.io/gh/brentyi/dcargs
.. |downloads| image:: https://pepy.tech/badge/dcargs
   :alt: Download count icon
   :target: https://pypi.org/project/dcargs/
.. |versions| image:: https://img.shields.io/pypi/pyversions/dcargs
   :alt: Version icon
   :target: https://pypi.org/project/dcargs/
.. |nbsp| unicode:: 0xA0
   :trim:
