What's supported
================

For minimum-boilerplate CLIs, :mod:`tyro` aims to maximize support of
Python's standard :mod:`typing` features.

Inputs can be annotated with:

- Basic types like :class:`int`, :class:`str`, :class:`float`, :class:`bool`, :class:`pathlib.Path`, :data:`None`.
- :class:`datetime.date`, :class:`datetime.datetime`, and :class:`datetime.time`.
- Container types like :class:`list`, :class:`dict`, :class:`tuple`, and :class:`set`.
- Union types, like ``X | Y``, :py:data:`typing.Union`, and :py:data:`typing.Optional`.
- :py:data:`typing.Literal` and :class:`enum.Enum`.
- Type aliases, for example using Python 3.12's `PEP 695 <https://peps.python.org/pep-0695/>`_ `type` statement.
- Generics, such as those annotated with :py:class:`typing.TypeVar` or with the type parameter syntax introduced by Python 3.12's `PEP 695 <https://peps.python.org/pep-0695/>`_.
- Compositions of the above types, like ``tuple[int | str, ...] | None``.


Types can also be placed and nested in various structures, such as:

- :func:`dataclasses.dataclass`.
- ``attrs``, ``pydantic``, ``ml_collections``, ``msgspec``, and ``flax.linen`` models.
- :py:class:`typing.NamedTuple`.
- :py:class:`typing.TypedDict`, including with flags like ``total=`` and associated annotations like :py:data:`typing.Required`, :py:data:`typing.NotRequired`, and :py:data:`typing.ReadOnly`.


What's not supported
--------------------


There are some limitations. We currently do not fully support:

- **Self-referential types.** For example, ``type RecursiveList[T] = T | list[RecursiveList[T]]``.
- **Variable-length sequences over nested structures**, unless a default is
  provided. For types like ``list[Dataclass]``, we require a default value to
  infer length from. The length of the corresponding field cannot be changed
  from the CLI interface.
- **Type parameters in class and static methods.** For example:

  .. code-block:: python

      class MyClass[T: int | str]:
        @staticmethod
        def method1(arg: T) -> T:
          return arg

        @classmethod
        def method2(cls, arg: T) -> T:
          return arg

      # The `int` type parameter will be ignored.
      tyro.cli(MyClass[int].method1)
      tyro.cli(MyClass[int].method2)

  This is because ``MyClass[int].method1`` / ``MyClass[int].method2`` cannot be
  distinguished from ``MyClass.method1`` / ``MyClass.method2`` at runtime.

For some of these cases, a :ref:`custom constructor
<example-category-custom_constructors>` can be defined as a workaround.
