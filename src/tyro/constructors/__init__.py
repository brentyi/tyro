"""The :mod:`tyro.constructors` submodule exposes tyro's API for defining
behavior for different types.

.. warning::

    This submodule is not needed for the majority of users.

"""

from .._singleton import MISSING as MISSING
from .._singleton import MISSING_NONPROP as MISSING_NONPROP
from ._primitive_spec import PrimitiveConstructorSpec as PrimitiveConstructorSpec
from ._primitive_spec import PrimitiveTypeInfo as PrimitiveTypeInfo
from ._primitive_spec import (
    UnsupportedTypeAnnotationError as UnsupportedTypeAnnotationError,
)
from ._registry import ConstructorRegistry as ConstructorRegistry
from ._struct_spec import StructConstructorSpec as StructConstructorSpec
from ._struct_spec import StructFieldSpec as StructFieldSpec
from ._struct_spec import StructTypeInfo as StructTypeInfo
