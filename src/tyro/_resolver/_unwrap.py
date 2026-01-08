"""Utilities for unwrapping Annotated, Final, ReadOnly, and resolving type aliases."""

from __future__ import annotations

import dataclasses
from typing import (
    Any,
    Callable,
    Literal,
    Tuple,
    TypeVar,
    Union,
    cast,
    overload,
)
from typing import (
    Type as TypeForm,
)

from typing_extensions import Annotated, TypeAliasType, get_args, get_origin

from .._typing_compat import (
    is_typing_final,
    is_typing_readonly,
    is_typing_typealiastype,
)
from ..conf import _confstruct

TypeOrCallable = TypeVar("TypeOrCallable", TypeForm[Any], Callable)
TypeOrCallableOrNone = TypeVar("TypeOrCallableOrNone", Callable, TypeForm[Any], None)
MetadataType = TypeVar("MetadataType")


@dataclasses.dataclass(frozen=True)
class TyroTypeAliasBreadCrumb:
    """A breadcrumb we can leave behind to track names of type aliases and
    `NewType` types. We can use type alias names to auto-populate
    subcommands."""

    name: str


def unwrap_origin_strip_extras(typ: TypeOrCallable) -> TypeOrCallable:
    """Returns the origin, ignoring typing.Annotated, of typ if it exists.

    This is a low-level utility that can be used at any stage of the type lifecycle.

    Args:
        typ: A type to extract the origin from.

    Returns:
        The origin of the type, or the type itself if no origin exists.
    """
    typ = unwrap_annotated(typ)
    origin = get_origin(typ)

    if origin is not None:
        typ = origin

    return typ


def resolve_newtype_and_aliases(
    typ: TypeOrCallableOrNone,
) -> TypeOrCallableOrNone:
    """Resolve NewType and TypeAliasType annotations.

    Unwraps NewType and Python 3.12+ `type` syntax aliases, adding
    TyroTypeAliasBreadCrumb annotations for name tracking.
    """
    # Fast path for plain types.
    if type(typ) is type:
        return typ

    # Handle type aliases, eg via the `type` statement in Python 3.12.
    if is_typing_typealiastype(type(typ)):
        typ_cast = cast(TypeAliasType, typ)
        return Annotated[  # type: ignore
            (
                cast(Any, resolve_newtype_and_aliases(typ_cast.__value__)),
                TyroTypeAliasBreadCrumb(typ_cast.__name__),
            )
        ]

    # We'll unwrap NewType annotations here; this is needed before issubclass
    # checks!
    #
    # `isinstance(x, NewType)` doesn't work because NewType isn't a class until
    # Python 3.10, so we instead do a duck typing-style check.
    return_name = None
    while hasattr(typ, "__name__") and hasattr(typ, "__supertype__"):
        if return_name is None:
            return_name = getattr(typ, "__name__")
        typ = resolve_newtype_and_aliases(getattr(typ, "__supertype__"))

    if return_name is not None:
        typ = Annotated[(typ, TyroTypeAliasBreadCrumb(return_name))]  # type: ignore

    return cast(TypeOrCallableOrNone, typ)


@overload
def unwrap_annotated(
    typ: Any,
    search_type: TypeForm[MetadataType],
) -> Tuple[Any, Tuple[MetadataType, ...]]: ...


@overload
def unwrap_annotated(
    typ: Any,
    search_type: Literal["all"],
) -> Tuple[Any, Tuple[Any, ...]]: ...


@overload
def unwrap_annotated(
    typ: Any,
    search_type: None = None,
) -> Any: ...


def unwrap_annotated(
    typ: Any,
    search_type: Union[TypeForm[MetadataType], Literal["all"], object, None] = None,
) -> Union[Tuple[Any, Tuple[MetadataType, ...]], Any]:
    """Helper for parsing typing.Annotated types.

    Strips one layer of Annotated and extracts metadata.

    Examples:
    - int, int => (int, ())
    - Annotated[int, 1], int => (int, (1,))
    - Annotated[int, "1"], int => (int, ())
    """

    # Fast path for plain types.
    # Note: isinstance(typ, type) filters out Annotated types automatically,
    # since Annotated[X] returns a typing._AnnotatedAlias, not a type.
    if isinstance(typ, type):
        # When search_type is None, we don't care about __tyro_markers__, so
        # we can return immediately for all plain types.
        if search_type is None:
            return typ
        elif not hasattr(typ, "__tyro_markers__"):
            return typ, ()

    # Unwrap aliases defined using Python 3.12's `type` syntax.
    typ = resolve_newtype_and_aliases(typ)

    # `Final` and `ReadOnly` types are ignored in tyro.
    orig = get_origin(typ)
    while is_typing_final(orig) or is_typing_readonly(orig):
        typ = get_args(typ)[0]
        orig = get_origin(typ)

    # Don't search for any annotations.
    if search_type is None:
        if not hasattr(typ, "__metadata__"):
            return typ
        else:
            return get_args(typ)[0]

    # Check for __tyro_markers__ from @configure. Use `__dict__` instead of
    # getattr() to prevent inheritance.
    if hasattr(typ, "__dict__") and "__tyro_markers__" in typ.__dict__:
        targets = tuple(
            x
            for x in typ.__dict__["__tyro_markers__"]
            if search_type == "all" or isinstance(x, search_type)  # type: ignore
        )
    else:
        targets = ()

    assert isinstance(targets, tuple)
    if not hasattr(typ, "__metadata__"):
        return typ, targets  # type: ignore

    args = get_args(typ)
    assert len(args) >= 2

    # Look through metadata for desired metadata type.
    targets += tuple(
        x
        for x in targets + args[1:]
        if search_type == "all" or isinstance(x, search_type)  # type: ignore
    )

    # Check for __tyro_markers__ in unwrapped type.
    if hasattr(args[0], "__tyro_markers__"):
        targets += tuple(
            x
            for x in getattr(args[0], "__tyro_markers__")
            if search_type == "all" or isinstance(x, search_type)  # type: ignore
        )
    return args[0], targets  # type: ignore


def swap_type_using_confstruct(typ: TypeOrCallable) -> TypeOrCallable:
    """Swap types using the `constructor_factory` attribute from
    `tyro.conf.arg` and `tyro.conf.subcommand`. Runtime annotations are
    kept, but the type is swapped."""
    # Need to swap types.
    _, annotations = unwrap_annotated(typ, search_type="all")
    for anno in reversed(annotations):
        if (
            isinstance(
                anno,
                (
                    _confstruct._ArgConfig,
                    _confstruct._SubcommandConfig,
                ),
            )
            and anno.constructor_factory is not None
        ):
            return Annotated[(anno.constructor_factory(),) + annotations]  # type: ignore
    return typ
