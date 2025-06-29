from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Dict

from typing_extensions import cast

from .. import _docstrings, _resolver
from .._singleton import MISSING_AND_MISSING_NONPROP, MISSING_NONPROP
from ._struct_spec import StructConstructorSpec, StructFieldSpec, StructTypeInfo

if TYPE_CHECKING:
    import pydantic as pydantic
    import pydantic.v1.fields as pydantic_v1_fields


def _get_pydantic_v1_field_default(
    name: str,
    field: pydantic_v1_fields.ModelField,
    parent_default_instance: Any,
) -> Any:
    """Helper for getting the default instance for a Pydantic field."""

    # Try grabbing default from parent instance.
    if (
        parent_default_instance not in MISSING_AND_MISSING_NONPROP
        and parent_default_instance is not None
    ):
        # Populate default from some parent, eg `default=` in `tyro.cli()`.
        if hasattr(parent_default_instance, name):
            return getattr(parent_default_instance, name)

    if not field.required:
        return field.get_default()

    # Otherwise, no default.
    return MISSING_NONPROP


def _get_pydantic_v2_field_default(
    name: str,
    field: pydantic.fields.FieldInfo,
    parent_default_instance: Any,
) -> Any:
    """Helper for getting the default instance for a Pydantic field."""

    # Try grabbing default from parent instance.
    if (
        parent_default_instance not in MISSING_AND_MISSING_NONPROP
        and parent_default_instance is not None
    ):
        # Populate default from some parent, eg `default=` in `tyro.cli()`.
        if hasattr(parent_default_instance, name):
            return getattr(parent_default_instance, name)

    if not field.is_required():
        return field.get_default(call_default_factory=True)

    # Otherwise, no default.
    return MISSING_NONPROP


def pydantic_rule(info: StructTypeInfo) -> StructConstructorSpec | None:
    """Rule for handling Pydantic models."""
    # Check if pydantic is imported
    if "pydantic" not in sys.modules.keys():  # pragma: no cover
        return None

    try:
        import pydantic
    except ImportError:
        # Needed for the mock import test in
        # test_missing_optional_packages.py to pass.
        return None

    try:
        if "pydantic.v1" in sys.modules.keys():
            from pydantic import v1 as pydantic_v1
        else:  # pragma: no cover
            pydantic_v1 = None  # type: ignore
    except ImportError:
        pydantic_v1 = None  # type: ignore

    # Check if the type is a Pydantic model
    try:
        if not (
            issubclass(info.type, pydantic.BaseModel)
            or (
                pydantic_v1 is not None and issubclass(info.type, pydantic_v1.BaseModel)
            )
        ):
            return None
    except TypeError:
        # issubclass failed!
        return None

    field_list = []
    pydantic_version = int(getattr(pydantic, "__version__", "1.0.0").partition(".")[0])

    if pydantic_version < 2 or (
        pydantic_v1 is not None and issubclass(info.type, pydantic_v1.BaseModel)
    ):
        # Pydantic 1.xx
        cls_cast = info.type
        hints = _resolver.get_type_hints_resolve_type_params(
            info.type, include_extras=True
        )
        for pd1_field in cast(Dict[str, Any], cls_cast.__fields__).values():
            helptext = pd1_field.field_info.description
            if helptext is None:
                helptext = _docstrings.get_field_docstring(
                    info.type, pd1_field.name, info.markers
                )

            default = _get_pydantic_v1_field_default(
                pd1_field.name, pd1_field, info.default
            )
            field_list.append(
                StructFieldSpec(
                    name=pd1_field.name,
                    type=hints[pd1_field.name],
                    default=default,
                    helptext=helptext,
                )
            )
    else:
        # Pydantic 2.xx
        hints = _resolver.get_type_hints_resolve_type_params(
            info.type, include_extras=True
        )
        for name, pd2_field in cast(Any, info.type).model_fields.items():
            helptext = pd2_field.description
            if helptext is None:
                helptext = _docstrings.get_field_docstring(
                    info.type, name, info.markers
                )

            default = _get_pydantic_v2_field_default(name, pd2_field, info.default)
            field_list.append(
                StructFieldSpec(
                    name=name,
                    type=hints[name],
                    default=default,
                    helptext=helptext,
                )
            )

    return StructConstructorSpec(instantiate=info.type, fields=tuple(field_list))
