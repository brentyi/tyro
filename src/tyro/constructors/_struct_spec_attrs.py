from __future__ import annotations

import functools
import sys
from typing import Any

from .. import _docstrings, _resolver
from .._singleton import MISSING_AND_MISSING_NONPROP, MISSING_NONPROP
from ._struct_spec import StructConstructorSpec, StructFieldSpec, StructTypeInfo


def attrs_rule(info: StructTypeInfo) -> StructConstructorSpec | None:
    """Rule for handling attrs classes."""
    # attr will already be imported if it's used.
    if "attr" not in sys.modules.keys():  # pragma: no cover
        return None

    try:
        import attr
    except ImportError:
        # This is needed for the mock import test in
        # test_missing_optional_packages.py to pass.
        return None

    if not attr.has(info.type):
        return None

    # We'll use our own type resolution system instead of attr's. This is
    # primarily to improve generics support.
    our_hints = _resolver.get_type_hints_resolve_type_params(
        info.type, include_extras=True
    )

    # Handle attr classes.
    field_list = []
    post_init_fields: dict[str, Any] = {}
    for attr_field in attr.fields(info.type):
        # Handle init=False fields separately.
        if not attr_field.init:
            # For init=False fields, we can't pass them to the constructor.
            # But we should preserve their values from the default instance.
            name = attr_field.name
            if info.default not in MISSING_AND_MISSING_NONPROP and hasattr(
                info.default, name
            ):
                post_init_fields[name] = getattr(info.default, name)
            continue

        # Default handling.
        name = attr_field.name
        default = attr_field.default
        if info.default not in MISSING_AND_MISSING_NONPROP:
            assert hasattr(info.default, name)
            default = getattr(info.default, name)
        elif default is attr.NOTHING:
            default = MISSING_NONPROP
        elif isinstance(default, attr.Factory):  # type: ignore
            default = default.factory()  # type: ignore

        assert attr_field.type is not None, attr_field
        field_list.append(
            StructFieldSpec(
                name=name,
                type=our_hints[name],
                default=default,
                helptext=functools.partial(
                    _docstrings.get_field_docstring, info.type, name, info.markers
                ),
            )
        )

    # Wrap the instantiate function if we have post-init fields to set.
    instantiate = info.type
    if len(post_init_fields) > 0:

        def wrapped_instantiate(**kwargs):
            instance = info.type(**kwargs)
            for field_name, field_value in post_init_fields.items():
                setattr(instance, field_name, field_value)
            return instance

        instantiate = wrapped_instantiate

    return StructConstructorSpec(
        instantiate=instantiate,
        fields=tuple(field_list),
    )
