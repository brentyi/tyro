Helptext generation
===================

:func:`tyro.cli()` automatically generates helptext for arguments from docstrings, comments, and annotations.
This functionality relies heavily on `docstring_parser <https://github.com/rr-/docstring_parser>`_.

Both callables (functions, objects with ``__call__`` methods) and "struct" types
(``dataclasses.dataclass``, ``NamedTuple``, ``TypedDict``, ``attrs``, ``pydantic``,
etc) are inspected for helptext.

Helptext from docstrings
------------------------

.. note::
   ✨ Docstrings are the recommended way to provide helptext! ✨

General callables
~~~~~~~~~~~~~~~~~

For general callables, field helptext is extracted from the corresponding field
docstring. Our examples use Google-style docstrings, but ReST, Numpydoc-style
and Epydoc docstrings are supported as well:

.. code-block:: python

    def main(field1: str, field2: int = 3) -> None:
        """Helptext for the overall CLI interface.

        Args:
            field1: Helptext for field1.
            field2: Helptext for field2.
        """
        print(field1, field2)

Struct types
~~~~~~~~~~~~

For fields defined using class attributes, enumerating arguments in class
docstrings can be cumbersome. :func:`tyro.cli` also supports helptext from
attribute docstrings:

.. code-block:: python

    @dataclasses.dataclass
    class Args:
        field1: str
        """Helptext for field1."""
        field2: int = 3
        """Helptext for field2."""

Helptext from comments
----------------------

For struct types, we also support helptext generation from comments.
This can be turned off using :data:`tyro.conf.HelptextFromCommentsOff`.

Inline comments
~~~~~~~~~~~~~~~

Inline comments can be more succinct than true attribute docstrings.

.. code-block:: python

    @dataclasses.dataclass
    class Args:
        field1: str  # Helptext for field1.
        field2: int = 3  # Helptext for field2.


Preceding comments
~~~~~~~~~~~~~~~~~~

These comments will apply to all fields that directly follow them. They can be
handy for semantically grouping fields, such as the two string fields below.

.. code-block:: python

    @dataclasses.dataclass
    class Args:
        # Strings. This will be displayed as helptext for both fields.
        field1: str
        field2: str
        # An integer field.
        # Multi-line comments are supported.
        field3: int


Helptext from annotations
-------------------------

tyro.conf.arg()
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:func:`tyro.conf.arg()` includes a ``help`` argument that can be used to provide helptext for a field.

.. code-block:: python

    @dataclasses.dataclass
    class Command:
        sources: Annotated[
            list[str],
            tyro.conf.arg(help="Filesystem locations or URLs."),
            # The 'help' argument will be become helptext for 'sources'
        ]

Doc objects
~~~~~~~~~~~

`PEP 727 <https://peps.python.org/pep-0727/>`_ proposes a ``Doc`` object for specifying introspectable documentation.

.. warning::
   As of this writing (2025-03-23), PEP 727 is in **draft** status.
   Please be advised that upstream support for this could
   `disappear <https://github.com/python/typing_extensions/issues/443>`_ from
   ``typing_extensions``.

.. code-block:: python


    from typing import Annotated
    from typing_extensions import Doc
    import dataclasses

    @dataclasses.dataclass
    class Config:
        input_file: Annotated[str, Doc("Path to the input file")]
        # The Doc string will become helptext for 'input-file'

Precedence rules
----------------

When multiple helptext sources are available, they are chosen in the
following order of precedence:

1. ``tyro.conf.arg()``
2. PEP 727 ``Doc``
3. Docstrings
4. Comments
