from __future__ import annotations

import sys

from .._docstrings import get_field_docstring
from .._resolver import get_type_hints_resolve_type_params
from .._singleton import MISSING, MISSING_NONPROP
from ._struct_spec import StructConstructorSpec, StructFieldSpec, StructTypeInfo


def msgspec_rule(info: StructTypeInfo) -> StructConstructorSpec | None:
    if "msgspec" not in sys.modules.keys():  # pragma: no cover
        return None

    import msgspec

    try:
        if not issubclass(info.type, msgspec.Struct):
            return None
    except TypeError:  # issubclass failed
        return None

    # Handle msgspec struct objects.
    field_list = []
    struct_type = msgspec.inspect.type_info(info.type)
    assert isinstance(struct_type, msgspec.inspect.StructType)

    # We need to use the original type hints, because `field.type` returns
    # a msgspec-specified type descriptor.
    annotations = get_type_hints_resolve_type_params(info.type, include_extras=True)

    for field in struct_type.fields:
        if info.default not in (
            MISSING,
            MISSING_NONPROP,
        ):
            default = getattr(info.default, field.name)
        elif field.default is not msgspec.NODEFAULT:
            default = field.default
        elif field.default_factory is not msgspec.NODEFAULT:
            default = field.default_factory()
        else:
            default = MISSING_NONPROP

        field_list.append(
            StructFieldSpec(
                name=field.name,
                type=annotations[field.name],
                default=default,
                helptext=get_field_docstring(info.type, field.name, info.markers),
            )
        )

    return StructConstructorSpec(instantiate=info.type, fields=tuple(field_list))
