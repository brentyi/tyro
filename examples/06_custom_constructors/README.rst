Custom constructors
===================

:func:`tyro.cli` is designed for comprehensive support of standard Python type
constructs. In some cases, however, it can be useful to extend the set of types
supported by :mod:`tyro`.

We provide two complementary approaches for doing so:

- :mod:`tyro.conf` provides a simple API for specifying custom constructor
  functions.
- :mod:`tyro.constructors` provides a more flexible API for defining behavior
  for different types. There are two categories of types: *primitive* types are
  instantiated from a single commandline argument, while *struct* types are
  broken down into multiple arguments.
