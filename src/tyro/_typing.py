"""tyro's API relies heavily on parsing type annotations, which may be both
"regular" types like `int`, `str`, and classes, or more general forms like `int
| str` or `Annotated[str, ...]`.

To correctly annotate variables that can take these more general type forms, we
need to wait for the typing.TypeForm PEP:

    https://peps.python.org/pep-0747/

This is still in draft form, so in the meantime we use Type[T] everywhere we would
otherwise have TypeForm[T]. This mostly works, and fortunately is supported by
pyright and pylance (relevant:
https://github.com/microsoft/pyright/issues/4298), but should be switched for
the correct typing.TypeForm annotation once it's available.

Also relevant:
- mypy support for typing_extensions.TypeForm: https://github.com/python/mypy/issues/9773
"""

from typing import Type as TypeForm

__all__ = ["TypeForm"]
