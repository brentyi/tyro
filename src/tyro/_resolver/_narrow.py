"""Type narrowing utilities for defaults and collections."""

from __future__ import annotations

import collections.abc
import warnings
from typing import (
    Any,
    Callable,
    List,
    Sequence,
    Set,
    Tuple,
    TypeVar,
    Union,
    cast,
)
from typing import (
    Type as TypeForm,
)

from typing_extensions import Annotated, get_args, get_origin

from .. import _unsafe_cache
from .._singleton import is_missing, is_sentinel
from .._typing_compat import is_typing_annotated, is_typing_union
from .._warnings import TyroWarning
from ._unwrap import (
    resolve_newtype_and_aliases,
    unwrap_annotated,
    unwrap_origin_strip_extras,
)
from ._utils import isinstance_with_fuzzy_numeric_tower

TypeOrCallable = TypeVar("TypeOrCallable", TypeForm[Any], Callable)


@_unsafe_cache.unsafe_cache(maxsize=1024)
def narrow_subtypes(
    typ: TypeOrCallable,
    default_instance: Any,
) -> TypeOrCallable:
    """Type narrowing: if we annotate as Animal but specify a default instance of Cat,
    we should parse as Cat.

    This should generally only be applied to fields used as nested structures, not
    individual arguments/fields. (if a field is annotated as Union[int, str], and a
    string default is passed in, we don't want to narrow the type to always be
    strings!)
    """

    typ = resolve_newtype_and_aliases(typ)

    if is_missing(default_instance):
        return typ

    try:
        potential_subclass = type(default_instance)

        if potential_subclass is type:
            # Don't narrow to `type`. This happens when the default instance is a class;
            # it doesn't really make sense to parse this case.
            return typ

        superclass = unwrap_annotated(typ)

        # For Python 3.10.
        if is_typing_union(get_origin(superclass)):
            return typ

        if superclass is Any or issubclass(potential_subclass, superclass):  # type: ignore
            if is_typing_annotated(get_origin(typ)):
                return Annotated[(potential_subclass,) + get_args(typ)[1:]]  # type: ignore
            typ = cast(TypeOrCallable, potential_subclass)
    except TypeError:
        # TODO: document where this TypeError can be raised, and reduce the amount of
        # code in it.
        pass

    return typ


def narrow_collection_types(
    typ: TypeOrCallable, default_instance: Any
) -> TypeOrCallable:
    """TypeForm narrowing for containers. Infers types of container contents."""

    # Can't narrow if we don't have a default value!
    if is_missing(default_instance):
        return typ

    # We'll recursively narrow contained types too!
    def _get_type(val: Any) -> TypeForm:
        return narrow_collection_types(type(val), val)

    args = get_args(typ)
    origin = get_origin(typ)

    # We should attempt to narrow if we see `list[Any]`, `tuple[Any]`,
    # `tuple[Any, ...]`, etc.
    if args == (Any,) or (origin is tuple and args == (Any, Ellipsis)):
        typ = origin  # type: ignore

    if typ in (list, Sequence, collections.abc.Sequence) and isinstance(
        default_instance, list
    ):
        if len(default_instance) == 0:
            return typ
        typ = List[Union[tuple(map(_get_type, default_instance))]]  # type: ignore
    elif typ in (set, Sequence, collections.abc.Sequence) and isinstance(
        default_instance, set
    ):
        if len(default_instance) == 0:
            return typ
        typ = Set[Union[tuple(map(_get_type, default_instance))]]  # type: ignore
    elif typ in (tuple, Sequence, collections.abc.Sequence) and isinstance(
        default_instance, tuple
    ):
        if len(default_instance) == 0:
            return typ
        default_types = tuple(map(_get_type, default_instance))
        if len(set(default_types)) == 1:
            typ = Tuple[default_types[0], Ellipsis]  # type: ignore
        else:
            typ = Tuple[default_types]  # type: ignore
    elif (
        origin is tuple
        and isinstance(default_instance, tuple)
        and len(args) == len(default_instance)
    ):
        typ = Tuple[
            tuple(
                _get_type(val_i) if typ_i is Any else typ_i
                for typ_i, val_i in zip(args, default_instance)
            )
        ]  # type: ignore
    return cast(TypeOrCallable, typ)


@_unsafe_cache.unsafe_cache(maxsize=1024)
def expand_union_types(typ: TypeOrCallable, default_instance: Any) -> TypeOrCallable:
    """Expand union types if necessary.

    This is a shim for failing more gracefully when we we're given a Union type that
    doesn't match the default value.

    In this case, we raise a warning, then add the type of the default value to the
    union. Loosely motivated by: https://github.com/brentyi/tyro/issues/20
    """
    if not is_typing_union(get_origin(typ)):
        return typ

    options = get_args(typ)
    options_unwrapped = [unwrap_origin_strip_extras(o) for o in options]

    try:
        # Skip expansion for sentinel values like EXCLUDE_FROM_CALL (from TypedDict
        # total=False), MISSING, and MISSING_NONPROP. These are not actual default
        # values and should not be added to the union type.
        if not is_sentinel(default_instance) and not any(
            isinstance_with_fuzzy_numeric_tower(default_instance, o) is not False
            for o in options_unwrapped
        ):
            warnings.warn(
                f"{type(default_instance)} does not match any type in Union:"
                f" {options_unwrapped}",
                category=TyroWarning,
            )
            return Union[options + (type(default_instance),)]  # type: ignore
    except TypeError:
        pass

    return typ
