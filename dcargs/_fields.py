"""Abstractions for pulling out 'field' abstractions, which specify inputs, from
general callables."""
import dataclasses
import inspect
import warnings
from typing import Any, Callable, List, Optional, Type, TypeVar

import docstring_parser
from typing_extensions import get_type_hints

from . import _docstrings, _resolver


@dataclasses.dataclass(frozen=True)
class Field:
    name: str
    typ: Type
    default: Any
    helptext: Optional[str]
    positional: bool


T = TypeVar("T")


def field_list_from_callable(
    f: Callable[..., T], default_instance: Optional[T]
) -> List[Field]:
    """Generate a list of generic 'field' objects corresponding to an input callable.

    `f` can be from a dataclass type, regular class type, or function."""

    # Unwrap generics.
    f, _unused_type_from_typevar = _resolver.resolve_generic_types(f)

    # Handling for class inputs vs function inputs.
    ignore_self = False
    cls: Optional[Type] = None
    if isinstance(f, type):
        # If `f` is a type:
        #     1. Set cls to the type.
        #     2. Consider `f` to be `cls.__init__`.
        cls = f
        f = cls.__init__  # type: ignore
        ignore_self = True

    # Get type annotations, docstrings.
    hints = get_type_hints(f)
    docstring = inspect.getdoc(f)
    docstring_from_arg_name = {}
    if docstring is not None:
        for param_doc in docstring_parser.parse(docstring).params:
            docstring_from_arg_name[param_doc.arg_name] = param_doc.description
    del docstring

    # Special handling for dataclasses: take `field(default_factory=...)` and
    # `default_instance` input into acocunt.
    default_from_dataclass_field_name = {}
    if cls is not None and _resolver.is_dataclass(cls):
        for field in _resolver.resolved_fields(cls):
            default_from_dataclass_field_name[
                field.name
            ] = _get_dataclass_field_default(field, default_instance)
    else:
        assert (
            default_instance is None
        ), "`default_instance` is only supported for dataclass types."

    # Generate field list from function signature.
    field_list = []
    for param in inspect.signature(f).parameters.values():
        # For `__init__`, skip self parameter.
        if ignore_self:
            ignore_self = False
            continue

        # Get default value.
        default = default_from_dataclass_field_name.get(param.name, param.default)
        if default is inspect.Parameter.empty:
            default = None

        # Get helptext from docstring.
        helptext = docstring_from_arg_name.get(param.name)
        if cls is not None:
            helptext = _docstrings.get_field_docstring(cls, param.name)

        field_list.append(
            Field(
                name=param.name,
                # Note that param.annotation does not resolve forward references.
                typ=hints[param.name],
                default=default,
                helptext=helptext,
                positional=param.kind is inspect.Parameter.POSITIONAL_ONLY,
            )
        )
    return field_list


def _ensure_dataclass_instance_used_as_default_is_frozen(
    field: dataclasses.Field, default_instance: Any
) -> None:
    """Ensure that a dataclass type used directly as a default value is marked as
    frozen."""
    assert dataclasses.is_dataclass(default_instance)
    cls = type(default_instance)
    if not cls.__dataclass_params__.frozen:
        warnings.warn(
            f"Mutable type {cls} is used as a default value for `{field.name}`. This is"
            " dangerous! Consider using `dataclasses.field(default_factory=...)` or"
            f" marking {cls} as frozen."
        )


def _get_dataclass_field_default(
    field: dataclasses.Field, parent_default_instance: Any
) -> Optional[Any]:
    """Helper for getting the default instance for a field."""
    field_default_instance = None
    if field.default is not dataclasses.MISSING:
        # Populate default from usual default value, or
        # `dataclasses.field(default=...)`.
        field_default_instance = field.default
        if dataclasses.is_dataclass(field_default_instance):
            _ensure_dataclass_instance_used_as_default_is_frozen(
                field, field_default_instance
            )
    elif field.default_factory is not dataclasses.MISSING:
        # Populate default from `dataclasses.field(default_factory=...)`.
        field_default_instance = field.default_factory()

    if parent_default_instance is not None:
        # Populate default from some parent, eg `default_instance` in `dcargs.cli()`.
        field_default_instance = getattr(parent_default_instance, field.name)
    return field_default_instance
