What's supported
================

For minimum-boilerplate CLIs, :mod:`tyro` aims to maximize support of
Python's standard :mod:`typing` features.

As a partial list, inputs can be annotated with:

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
- ``attrs``, ``pydantic``, and ``flax.linen`` models.
- :py:class:`typing.NamedTuple`.
- :py:class:`typing.TypedDict`, flags like ``total=``, and associated annotations like :py:data:`typing.Required`, :py:data:`typing.NotRequired`, :py:data:`typing.ReadOnly`,


What's not supported
--------------------


There are some limitations. We currently *do not* support:

- Variable-length sequences over nested structures, unless a default is
  provided. For types like ``list[Dataclass]``, we require a default value to
  infer length from. The length of the corresponding field cannot be changed
  from the CLI interface.
- Nesting variable-length sequences in other sequences. ``tuple[int, ...]`` and
  ``tuple[tuple[int, int, int], ...]`` are supported, as the variable-length
  sequence is the outermost type. However, ``tuple[tuple[int, ...], ...]`` is
  ambiguous to parse and not supported.
- Self-referential types, like ``type RecursiveList[T] = T | list[RecursiveList[T]]``.

In each of these cases, a :ref:`custom constructor
<example-category-custom_constructors>` can be defined as a workaround.
