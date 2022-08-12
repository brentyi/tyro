"""Abstractions for pulling out 'field' definitions, which specify inputs, types, and
defaults, from general callables."""

import collections
import dataclasses
import inspect
import itertools
import typing
import warnings
from typing import (
    Any,
    Callable,
    Hashable,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    cast,
    get_args,
)

import docstring_parser
import typing_extensions
from typing_extensions import get_type_hints, is_typeddict

from . import _docstrings, _instantiators, _resolver


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


class PropagatingMissingType(_Singleton):
    pass


class NonpropagatingMissingType(_Singleton):
    pass


class ExcludeFromCallType(_Singleton):
    pass


# We have two types of missing sentinels: a propagating missing value, which when set as
# a default will set all child values of nested structures as missing as well, and a
# nonpropagating missing sentinel, which does not override child defaults.
MISSING_PROP = PropagatingMissingType()
MISSING_NONPROP = NonpropagatingMissingType()
EXCLUDE_FROM_CALL = ExcludeFromCallType()

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

DefaultInstanceT = Union[T, PropagatingMissingType, NonpropagatingMissingType]

_known_parsable_types = set(
    filter(
        lambda x: isinstance(x, Hashable),  # type: ignore
        itertools.chain(
            __builtins__.values(),  # type: ignore
            vars(typing).values(),
            vars(typing_extensions).values(),
            vars(collections.abc).values(),
        ),
    )
)


def is_possibly_nested_type(typ: Any, default_instance: Any) -> bool:
    """Determine whether a type can be treated as a 'nested type', where a single field
    has multiple corresponding arguments (eg for nested dataclasses or classes)."""

    try:
        # This implementation will result in some computational redundancy, but is nice
        # for reusing logic. Should be revisited.
        field_list_from_callable(typ, default_instance, root_field=False)
        return True
    except _instantiators.UnsupportedTypeAnnotationError:
        return False


def field_list_from_callable(
    f: Callable[..., T],
    default_instance: DefaultInstanceT,
    root_field: bool = False,
) -> List[FieldDefinition]:
    """Generate a list of generic 'field' objects corresponding to the inputs of some
    annotated callable.

    `f` can be from a dataclass type, regular class type, or function.

    If `root_field` is set to True, we treat `int`, `torch.device`, etc as nested
    fields. This is to make sure that these types can be passed directly into
    dcargs.cli(); the logic can likely be refactored."""

    # Unwrap generics.
    f, type_from_typevar = _resolver.resolve_generic_types(f)

    # If `f` is a type:
    #     1. Set cls to the type.
    #     2. Consider `f` to be `cls.__init__`.
    cls: Optional[Type] = None
    if isinstance(f, type):
        cls = f
        f = cls.__init__  # type: ignore

    # Handle each supported nested structure type.
    if cls is not None and is_typeddict(cls):
        return _field_list_from_typeddict(cls, default_instance)

    elif cls is not None and _resolver.is_namedtuple(cls):
        return _field_list_from_namedtuple(cls, default_instance)

    elif cls is not None and _resolver.is_dataclass(cls):
        return _field_list_from_dataclass(cls, default_instance)

    elif _resolver.unwrap_origin(f) is tuple:
        assert cls is None
        return _field_list_from_tuple(f, default_instance)

    elif not root_field and (
        (cls is not None and cls in _known_parsable_types)
        or _resolver.unwrap_origin(f) in _known_parsable_types
    ):
        raise _instantiators.UnsupportedTypeAnnotationError(
            f"{f} cannot be interpreted as a nested structure!"
        )

    else:
        return _field_list_from_general_callable(
            f, cls, default_instance, root_field=root_field
        )


def _field_list_from_typeddict(
    cls: Type[T], default_instance: DefaultInstanceT
) -> List[FieldDefinition]:
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
            if is_possibly_nested_type(typ, MISSING_NONPROP):
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


def _field_list_from_namedtuple(
    cls: Type[T], default_instance: DefaultInstanceT
) -> List[FieldDefinition]:
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


def _field_list_from_dataclass(
    cls: Type[T], default_instance: DefaultInstanceT
) -> List[FieldDefinition]:
    # Handle dataclasses.
    field_list = []
    for dc_field in filter(lambda field: field.init, _resolver.resolved_fields(cls)):
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


def _field_list_from_tuple(
    f: Callable, default_instance: DefaultInstanceT
) -> List[FieldDefinition]:
    # Fixed-length tuples.
    field_list = []
    children = get_args(f)
    if Ellipsis in children:
        raise _instantiators.UnsupportedTypeAnnotationError(
            "For nested structures, only fixed-length tuples are allowed."
        )

    if default_instance in MISSING_SINGLETONS:
        default_instance = (default_instance,) * len(children)
    assert len(default_instance) == len(  # type: ignore
        children
    ), "Tuple: length of annotation and type don't match."

    for i, child in enumerate(children):
        default_i = default_instance[i]  # type: ignore
        field_list.append(
            FieldDefinition(
                # We'd use an index operator h
                name=str(i),
                typ=child,
                default=default_i,
                helptext="",
                # This should really be positional=True, but the CLI is more
                # intuitive for mixed nested/non-nested types in tuples when we
                # stick with kwargs. Tuples are special-cased in _calling.py.
                positional=False,
            )
        )

    contains_nested = False
    for field in field_list:
        contains_nested |= is_possibly_nested_type(field.typ, field.default)
    if not contains_nested:
        # We could also check for variable length children, which can be populated when
        # the tuple is interpreted as a nested field but not a directly parsed one.
        raise _instantiators.UnsupportedTypeAnnotationError(
            "Tuple does not contain any nested structures."
        )

    return field_list


def _field_list_from_general_callable(
    f: Callable,
    cls: Optional[Type],
    default_instance: DefaultInstanceT,
    root_field: bool,
) -> List[FieldDefinition]:
    # Handle general callables.
    if default_instance not in MISSING_SINGLETONS:
        raise _instantiators.UnsupportedTypeAnnotationError(
            "`default_instance` is not supported in this context."
        )

    # Generate field list from function signature.
    if not callable(f):
        raise _instantiators.UnsupportedTypeAnnotationError(
            f"Cannot extract annotations from {f}, which is not a callable type."
        )
    params = list(inspect.signature(f).parameters.values())
    if cls is not None:
        # Ignore self parameter.
        params = params[1:]

    try:
        return _field_list_from_params(f, cls, params)
    except (_instantiators.UnsupportedTypeAnnotationError, TypeError) as e:
        if not root_field:
            raise e

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

    # This will throw a type error for torch.device, typing.Dict, etc.
    try:
        hints = get_type_hints(f)
    except TypeError:
        raise _instantiators.UnsupportedTypeAnnotationError(
            f"Could not get hints for {f}!"
        )

    field_list = []
    for param in params:
        # Get default value.
        default = param.default

        # Get helptext from docstring.
        helptext = docstring_from_arg_name.get(param.name)
        if helptext is None and cls is not None:
            helptext = _docstrings.get_field_docstring(cls, param.name)

        if param.name not in hints:
            raise _instantiators.UnsupportedTypeAnnotationError(
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
