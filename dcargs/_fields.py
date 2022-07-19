"""Abstractions for pulling out 'field' definitions, which specify inputs, types, and
defaults, from general callables."""

import dataclasses
import inspect
import warnings
from typing import Any, Callable, List, Optional, Type, TypeVar, Union, cast

import docstring_parser
from typing_extensions import get_type_hints, is_typeddict

from . import _docstrings, _instantiators, _parsers, _resolver


@dataclasses.dataclass(frozen=True)
class FieldDefinition:
    name: str
    typ: Type
    default: Any
    helptext: Optional[str]
    positional: bool


class _Singleton:
    # Singleton pattern.
    # https://www.python.org/download/releases/2.2/descrintro/#__new__
    def __new__(cls, *args, **kwds):
        it = cls.__dict__.get("__it__")
        if it is not None:
            return it
        cls.__it__ = it = object.__new__(cls)
        it.init(*args, **kwds)
        return it

    def init(self, *args, **kwds):
        pass


class PropagatingMissingType(_Singleton):  # pragma: no cover
    pass


class NonpropagatingMissingType(_Singleton):
    pass


class ExcludeFromKwargsType(_Singleton):
    pass


# We have two types of missing sentinels: a propagating missing value, which when set as
# a default will set all child values of nested structures as missing as well, and a
# nonpropagating missing sentinel, which does not override child defaults.
MISSING_PROP = PropagatingMissingType()
MISSING_NONPROP = NonpropagatingMissingType()
EXCLUDE_FROM_CALL = ExcludeFromKwargsType()

# Note that our "public" missing API will always be the propagating missing sentinel.
MISSING_PUBLIC: Any = MISSING_PROP
"""Sentinel value to mark fields as missing. Can be used to mark fields passed in as a
`default_instance` for `dcargs.cli()` as required."""


MISSING_TYPE = Union[PropagatingMissingType, NonpropagatingMissingType]
MISSING_SINGLETONS = [
    dataclasses.MISSING,
    MISSING_PROP,
    MISSING_NONPROP,
    inspect.Parameter.empty,
]
try:
    # Undocumented feature: support omegaconf dataclasses out of the box.
    import omegaconf

    MISSING_SINGLETONS.append(omegaconf.MISSING)
except ImportError:
    pass

T = TypeVar("T")


def field_list_from_callable(
    f: Callable[..., T],
    default_instance: Union[T, PropagatingMissingType, NonpropagatingMissingType],
) -> List[FieldDefinition]:
    """Generate a list of generic 'field' objects corresponding to the inputs of some
    annotated callable.

    `f` can be from a dataclass type, regular class type, or function."""

    # Unwrap generics.
    f, type_from_typevar = _resolver.resolve_generic_types(f)

    # If `f` is a type:
    #     1. Set cls to the type.
    #     2. Consider `f` to be `cls.__init__`.
    cls: Optional[Type] = None
    if isinstance(f, type):
        cls = f
        f = cls.__init__  # type: ignore

    if cls is not None and is_typeddict(cls):
        # Handle typed dictionaries.
        field_list = []
        valid_default_instance = (
            default_instance not in MISSING_SINGLETONS
            and default_instance is not EXCLUDE_FROM_CALL
        )
        assert not valid_default_instance or isinstance(default_instance, dict)
        for name, typ in get_type_hints(cls).items():
            if valid_default_instance:
                default = default_instance.get(name, MISSING_PROP)  # type: ignore
            elif getattr(cls, "__total__") is False:
                default = EXCLUDE_FROM_CALL
                if _parsers.is_possibly_nested_type(typ):
                    raise _instantiators.UnsupportedTypeAnnotationError(
                        "`total=False` not supported for nested structures."
                    )
            else:
                default = MISSING_PROP

            field_list.append(
                FieldDefinition(
                    name=name,
                    typ=typ,
                    default=default,
                    helptext=_docstrings.get_field_docstring(cls, name),
                    positional=False,
                )
            )
        return field_list
    elif cls is not None and _resolver.is_namedtuple(cls):
        # Handle NamedTuples.
        #
        # TODO: in terms of helptext, we currently do display the default NamedTuple
        # helptext. But we (intentionally) don't for dataclasses; this is somewhat
        # inconsistent.
        field_list = []
        field_defaults = getattr(cls, "_field_defaults")

        # Note that _field_types is removed in Python 3.9.
        for name, typ in _resolver.get_type_hints(cls).items():
            # Get default, with priority for `default_instance`.
            default = field_defaults.get(name, MISSING_NONPROP)
            if hasattr(default_instance, name):
                default = getattr(default_instance, name)
            if default_instance is MISSING_PROP:
                default = MISSING_PROP

            field_list.append(
                FieldDefinition(
                    name=name,
                    typ=typ,
                    default=default,
                    helptext=_docstrings.get_field_docstring(cls, name),
                    positional=False,
                )
            )
        return field_list
    elif cls is not None and _resolver.is_dataclass(cls):
        # Handle dataclasses.
        field_list = []
        for dc_field in filter(
            lambda field: field.init, _resolver.resolved_fields(cls)
        ):
            default = _get_dataclass_field_default(dc_field, default_instance)
            field_list.append(
                FieldDefinition(
                    name=dc_field.name,
                    typ=dc_field.type,
                    default=default,
                    helptext=_docstrings.get_field_docstring(cls, dc_field.name),
                    positional=False,
                )
            )
        return field_list
    else:
        # Handle general callables.
        assert (
            default_instance in MISSING_SINGLETONS
        ), "`default_instance` is only supported for dataclass and TypedDict types."

        # Generate field list from function signature.
        field_list = []
        params = list(inspect.signature(f).parameters.values())
        if cls is not None:
            # Ignore self parameter.
            params = params[1:]

        try:
            return _field_list_from_params(f, cls, params)
        except TypeError as e:
            # Try to support passing things like int, str, Dict[K,V], torch.device
            # directly into dcargs.cli(). These aren't "type-annotated callables" but
            # this a nice-to-have.
            param_count = 0
            has_kw_only = False
            has_var_positional = False
            for param in params:
                if (
                    param.kind
                    in (
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    )
                    and param.default is inspect.Parameter.empty
                ):
                    param_count += 1
                elif param.kind is inspect.Parameter.KEYWORD_ONLY:
                    has_kw_only = True
                elif param.kind is inspect.Parameter.VAR_POSITIONAL:
                    has_var_positional = True

            if not has_kw_only and (
                param_count == 1 or (param_count == 0 and has_var_positional)
            ):
                # Things look ok!
                if cls is not None:
                    f = cls
                return [
                    FieldDefinition(
                        name=_resolver.unwrap_origin(f).__name__,
                        typ=cast(Type, f),
                        default=MISSING_NONPROP,
                        helptext=None,
                        positional=True,
                    )
                ]
            else:
                raise e


def _field_list_from_params(
    f: Callable, cls: Optional[Type], params: List[inspect.Parameter]
) -> List[FieldDefinition]:
    # Get type annotations, docstrings.
    docstring = inspect.getdoc(f)
    docstring_from_arg_name = {}
    if docstring is not None:
        for param_doc in docstring_parser.parse(docstring).params:
            docstring_from_arg_name[param_doc.arg_name] = param_doc.description
    del docstring
    hints = get_type_hints(f)

    field_list = []
    for param in params:
        # Get default value.
        default = param.default

        # Get helptext from docstring.
        helptext = docstring_from_arg_name.get(param.name)
        if helptext is None and cls is not None:
            helptext = _docstrings.get_field_docstring(cls, param.name)

        if param.name not in hints:
            raise TypeError(
                f"Expected fully type-annotated callable, but {f} with arguments"
                f" {tuple(map(lambda p: p.name, params))} has no annotation for"
                f" '{param.name}'."
            )

        field_list.append(
            FieldDefinition(
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
    # If the dataclass's parent is explicitly marked MISSING, mark this field as missing
    # as well.
    if parent_default_instance is MISSING_PROP:
        return MISSING_PROP

    # Try grabbing default from parent instance.
    if (
        parent_default_instance not in MISSING_SINGLETONS
        and parent_default_instance is not None
    ):
        # Populate default from some parent, eg `default_instance` in `dcargs.cli()`.
        if hasattr(parent_default_instance, field.name):
            return getattr(parent_default_instance, field.name)
        else:
            warnings.warn(
                f"Could not find field {field.name} in default instance"
                f" {parent_default_instance}, which has"
                f" type {type(parent_default_instance)},",
                stacklevel=2,
            )

    # Try grabbing default from dataclass field.
    if field.default not in MISSING_SINGLETONS:
        default = field.default
        if dataclasses.is_dataclass(default):
            _ensure_dataclass_instance_used_as_default_is_frozen(field, default)
        return default

    # Populate default from `dataclasses.field(default_factory=...)`.
    if field.default_factory is not dataclasses.MISSING and not (
        # Special case to ignore default_factory if we write:
        # `field: Dataclass = dataclasses.field(default_factory=Dataclass)`.
        #
        # In other words, treat it the same way as:
        # `field: Dataclass`.
        #
        # The only time this matters is when we our dataclass has a `__post_init__`
        # function that mutates the dataclass. We choose here to use the default values
        # before this method is called.
        dataclasses.is_dataclass(field.type)
        and field.default_factory is field.type
    ):
        return field.default_factory()

    # Otherwise, no default. This is different from MISSING, because MISSING propagates
    # to children. We could revisit this design to make it clearer.
    return MISSING_NONPROP
