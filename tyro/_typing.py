# tyro's API relies heavily on parsing type annotations, which may be both "regular"
# types like `int`, `str`, and classes, or more general forms like `int | str` or
# `Annotated[str, ...]`.
#
# To correctly annotate variables that can take these more general type forms, we need
# to wait for a typing.TypeForm PEP:
#     https://github.com/python/mypy/issues/9773
#
# This doesn't yet exist, so in the meantime we use Type[T] everywhere we would
# otherwise have TypeForm[T]. This mostly works, and fortunately is supported by pyright
# and pylance (relevant: https://github.com/microsoft/pyright/issues/4298), but should
# be switched for the correct typing.TypeForm annotation once it's available.

from typing import Type as TypeForm

__all__ = ["TypeForm"]
