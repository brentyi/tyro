import dataclasses
import functools
from typing import Any, Callable, List, Optional, Protocol, Tuple, Type, TypeVar, Union

from typing_extensions import Annotated

from .. import _resolver
from .._typing import TypeForm

T = TypeVar("T")

MatchingFunction = Callable[[Type], bool]
ConstructorFactoryFunction = Callable[[Type[T], T], Callable[..., T]]


registered_constructors: List[Tuple[MatchingFunction, ConstructorFactoryFunction]] = []


def register_constructor(
    matcher: MatchingFunction,
    constructor_factory: ConstructorFactoryFunction,
) -> None:
    """Register custom constructors.

    When tyro encounters a type `t` where `matcher(t)` is True, it will be parsed using
    the signature of the function returned by `constructor_factory(t)` instead of the
    default constructor."""
    registered_constructors.append((matcher, constructor_factory))


# Be a little bit permissive with types here, since we often blur the lines between
# Callable[..., T] and TypeForm[T]... this could be cleaned up!
TypeT = TypeVar("TypeT", bound=Union[TypeForm, Callable])


builtsin_registered = False


def get_constructor_for_type(typ: TypeT, default: Any) -> TypeT:
    global builtins_registered
    if not builtsin_registered:
        from . import _extensions

        _extensions.register_builtins()
        builtins_registered = True

    for matcher, constructor_factory in registered_constructors:
        if matcher(typ):
            return constructor_factory(typ, default)  # type: ignore

    return typ
