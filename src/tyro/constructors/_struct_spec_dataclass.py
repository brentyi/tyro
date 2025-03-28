from __future__ import annotations

import dataclasses
import warnings
from typing import Any, cast

from .. import _docstrings, _resolver
from .._singleton import MISSING, MISSING_AND_MISSING_NONPROP, MISSING_NONPROP
from ._struct_spec import StructConstructorSpec, StructFieldSpec, StructTypeInfo
from ._struct_spec_flax import is_flax_module


def _ensure_dataclass_instance_used_as_default_is_frozen(
    field: dataclasses.Field, default_instance: Any
) -> None:
    """Ensure that a dataclass type used directly as a default value is marked as
    frozen."""
    assert dataclasses.is_dataclass(default_instance)
    cls = type(default_instance)
    if not cls.__dataclass_params__.frozen:  # type: ignore
        warnings.warn(
            f"Mutable type {cls} is used as a default value for `{field.name}`. This is"
            " dangerous! Consider using `dataclasses.field(default_factory=...)` or"
            f" marking {cls} as frozen."
        )


def _get_dataclass_field_default(
    field: dataclasses.Field, parent_default_instance: Any
) -> Any:
    """Helper for getting the default instance for a dataclass field."""
    # If the dataclass's parent is explicitly marked MISSING, mark this field as missing
    # as well.
    if parent_default_instance is MISSING:
        return MISSING

    # Try grabbing default from parent instance.
    if (
        parent_default_instance not in MISSING_AND_MISSING_NONPROP
        and parent_default_instance is not None
    ):
        # Populate default from some parent, eg `default=` in `tyro.cli()`.
        if hasattr(parent_default_instance, field.name):
            return getattr(parent_default_instance, field.name)

    # Try grabbing default from dataclass field.
    if field.default is not dataclasses.MISSING:
        default = field.default
        # dataclasses.is_dataclass() will also return true for dataclass
        # _types_, not just instances.
        if type(default) is not type and dataclasses.is_dataclass(default):
            _ensure_dataclass_instance_used_as_default_is_frozen(field, default)
        return default

    # Populate default from `dataclasses.field(default_factory=...)`.
    if field.default_factory is not dataclasses.MISSING and not (
        # Special case to ignore default_factory if we write:
        # `field: Dataclass = dataclasses.field(default_factory=Dataclass)`.
        #
        # In other words, treat it the same way as: `field: Dataclass`.
        #
        # The only time this matters is when we our dataclass has a `__post_init__`
        # function that mutates the dataclass. We choose here to use the default values
        # before this method is called.
        dataclasses.is_dataclass(field.type) and field.default_factory is field.type
    ):
        return field.default_factory()

    # Otherwise, no default.
    return MISSING_NONPROP


def dataclass_rule(info: StructTypeInfo) -> StructConstructorSpec | None:
    """Rule for handling dataclass types."""
    if not dataclasses.is_dataclass(info.type):
        return None

    # Check if this is a flax module and get fields to skip
    is_flax, flax_skip_fields = is_flax_module(info.type)

    # Handle dataclasses.
    field_list = []
    for dc_field in filter(
        lambda field: field.init, _resolver.resolved_fields(info.type)
    ):
        # For flax modules, we ignore the built-in fields.
        if is_flax and dc_field.name in flax_skip_fields:
            continue

        default = _get_dataclass_field_default(dc_field, info.default)

        # Try to get helptext from field metadata. This is also intended to be
        # compatible with HuggingFace-style config objects.
        helptext = dc_field.metadata.get("help", None)
        assert isinstance(helptext, (str, type(None)))

        # Try to get helptext from docstrings. This can't be generated
        # dynamically.
        if helptext is None:
            helptext = _docstrings.get_field_docstring(
                info.type, dc_field.name, info.markers
            )

        assert not isinstance(dc_field.type, str)
        field_list.append(
            StructFieldSpec(
                name=dc_field.name,
                type=cast(Any, dc_field.type),
                default=default,
                helptext=helptext,
            )
        )
    return StructConstructorSpec(instantiate=info.type, fields=tuple(field_list))
