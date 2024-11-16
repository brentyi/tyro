Custom constructors
===================

In these examples, we show how custom types can be parsed by and registered
with :func:`tyro.cli`. This can be used to extend the set of types supported by
:mod:`tyro`.

We provide two ways of doing this:
* :mod:`tyro.conf` provides a simple API for specifying custom constructor
  functions.
* :mod:`tyro.constructors` provides a more flexible API for defining behavior
  for different types. There are two categories of types: *primitive* types are
  instantiated from a single commandline argument, while *struct* types are
  broken down into multiple arguments.
