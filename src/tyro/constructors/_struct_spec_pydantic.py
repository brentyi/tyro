from __future__ import annotations

import functools
import sys
from typing import TYPE_CHECKING, Any, Dict

from typing_extensions import cast

from .. import _docstrings, _resolver
from .._singleton import MISSING_NONPROP, is_missing
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
    if not is_missing(parent_default_instance) and parent_default_instance is not None:
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
    if not is_missing(parent_default_instance) and parent_default_instance is not None:
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
    # Pydantic validates input by alias (not field name) unless the model is
    # configured with populate_by_name. We key our fields/flags by the Python
    # field name but must construct with the alias, so map name -> input alias
    # for any field that declares one. (Complex aliases like AliasChoices/
    # AliasPath are left alone and fall back to the field name.)
    alias_from_name: Dict[str, str] = {}
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
                helptext = functools.partial(
                    _docstrings.get_field_docstring,
                    info.type,
                    pd1_field.name,
                    info.markers,
                )

            default = _get_pydantic_v1_field_default(
                pd1_field.name, pd1_field, info.default
            )
            pd1_alias = getattr(pd1_field, "alias", None)
            if isinstance(pd1_alias, str) and pd1_alias != pd1_field.name:
                alias_from_name[pd1_field.name] = pd1_alias
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
                helptext = functools.partial(
                    _docstrings.get_field_docstring, info.type, name, info.markers
                )

            default = _get_pydantic_v2_field_default(name, pd2_field, info.default)
            # The name pydantic accepts on input is the validation alias when
            # set (for a plain `alias=`, pydantic auto-populates validation_alias
            # with it). A non-string validation_alias (AliasChoices/AliasPath)
            # has no single flat input name, so we must NOT fall back to the
            # serialization-side `.alias` there: construct by field name instead
            # (accepted when populate_by_name is set), matching pre-fix behavior.
            va = pd2_field.validation_alias
            if isinstance(va, str):
                input_name = va
            elif va is None and isinstance(pd2_field.alias, str):
                input_name = pd2_field.alias
            else:
                input_name = None
            if input_name is not None and input_name != name:
                alias_from_name[name] = input_name
            field_list.append(
                StructFieldSpec(
                    name=name,
                    type=hints[name],
                    default=default,
                    helptext=helptext,
                )
            )

    instantiate: Any
    if alias_from_name:
        model_cls = info.type

        def instantiate_with_aliases(**kwargs: Any) -> Any:
            return model_cls(
                **{alias_from_name.get(k, k): v for k, v in kwargs.items()}
            )

        instantiate = instantiate_with_aliases
    else:
        instantiate = info.type

    return StructConstructorSpec(instantiate=instantiate, fields=tuple(field_list))
