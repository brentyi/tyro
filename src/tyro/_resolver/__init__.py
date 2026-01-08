"""Resolver utilities for type resolution, unwrapping, and narrowing.

This package provides utilities for:
- TypeVar resolution (TypeParamResolver, TypeParamAssignmentContext)
- Unwrapping Annotated, Final, ReadOnly types
- Type narrowing based on default values
- Type inspection utilities
"""

from ._narrow import (
    expand_union_types as expand_union_types,
)
from ._narrow import (
    narrow_collection_types as narrow_collection_types,
)
from ._narrow import (
    narrow_subtypes as narrow_subtypes,
)
from ._typevar import (
    TypeParamAssignmentContext as TypeParamAssignmentContext,
)
from ._typevar import (
    TypeParamResolver as TypeParamResolver,
)
from ._typevar import (
    get_type_hints_resolve_type_params as get_type_hints_resolve_type_params,
)
from ._typevar import (
    resolve_generic_types as resolve_generic_types,
)
from ._unwrap import (
    TyroTypeAliasBreadCrumb as TyroTypeAliasBreadCrumb,
)
from ._unwrap import (
    resolve_newtype_and_aliases as resolve_newtype_and_aliases,
)
from ._unwrap import (
    swap_type_using_confstruct as swap_type_using_confstruct,
)
from ._unwrap import (
    unwrap_annotated as unwrap_annotated,
)
from ._unwrap import (
    unwrap_origin_strip_extras as unwrap_origin_strip_extras,
)
from ._utils import (
    is_dataclass as is_dataclass,
)
from ._utils import (
    is_instance as is_instance,
)
from ._utils import (
    is_namedtuple as is_namedtuple,
)
from ._utils import (
    isinstance_with_fuzzy_numeric_tower as isinstance_with_fuzzy_numeric_tower,
)
from ._utils import (
    resolved_fields as resolved_fields,
)
