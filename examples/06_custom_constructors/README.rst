Custom constructors
===================

:func:`tyro.cli` aims for comprehensive support of standard Python type
constructs. It can still, however, be useful to extend the set of suported
types.

We provide two complementary approaches for doing so:

- :mod:`tyro.conf` provides a simple API for specifying custom constructor
  functions.
- :mod:`tyro.constructors` provides a more flexible API for defining behavior
  for different types. There are two categories of types: *primitive* types are
  instantiated from a single commandline argument, while *struct* types are
  broken down into multiple arguments.

.. warning::

    Custom constructors are useful, but can be verbose and require care. We
    recommend using them sparingly.
