"""Helper for using type annotations to recursively generate instantiator functions,
which map strings (or, in some cases, sequences of strings) to the annotated type.

Some examples of type annotations and the desired instantiators:
```
    int

        lambda string: int(str)

    List[int]

        lambda strings: list(
            [int(x) for x in strings]
        )

    List[Color], where Color is an enum

        lambda strings: list(
            [Color[x] for x in strings]
        )

    Tuple[int, float]

        lambda strings: tuple(
            [
                typ(x)
                for typ, x in zip(
                    (int, float),
                    strings,
                )
            ]
        )
```
"""

import collections
import dataclasses
import enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, Union

from typing_extensions import Final, Literal, _AnnotatedAlias, get_args, get_origin

from . import _strings

Instantiator = Union[
    # Most standard fields: these are converted from strings from the CLI.
    Callable[[str], Any],
    # Sequence fields! This should be used whenever argparse's `nargs` field is set.
    Callable[[List[str]], Any],
    # Special case: the only time that argparse doesn't give us a string is when the
    # argument action is set to `store_true` or `store_false`. In this case, we get
    # a bool directly, and the field action can be a no-op.
    Callable[[bool], bool],
]


@dataclasses.dataclass
class InstantiatorMetadata:
    nargs: Optional[Union[str, int]]
    metavar: Union[str, Tuple[str, ...]]
    choices: Optional[Tuple[Any, ...]]
    is_optional: bool


class UnsupportedTypeAnnotationError(Exception):
    """Exception raised when field actions fail; this typically means that values from
    the CLI are invalid."""


def instantiator_from_type(
    typ: Type, type_from_typevar: Dict[TypeVar, Type]
) -> Tuple[Instantiator, InstantiatorMetadata]:
    """Recursive helper for parsing type annotations.

    Returns two things:
    - An instantiator function, for instantiating the type from a string or list of
      strings. The latter applies when argparse's `nargs` parameter is set.
    - A metadata structure, which specifies parameters for argparse.
    """

    # Resolve typevars.
    if typ in type_from_typevar:
        return instantiator_from_type(
            type_from_typevar[typ],  # type: ignore
            type_from_typevar,
        )

    # Address container types. If a matching container is found, this will recursively
    # call instantiator_from_type().
    container_out = _instantiator_from_container_type(typ, type_from_typevar)
    if container_out is not None:
        return container_out

    # Construct instantiators for raw types.
    auto_choices: Optional[Tuple[str, ...]] = None
    if typ is bool:
        auto_choices = ("True", "False")
    elif issubclass(typ, enum.Enum):
        auto_choices = tuple(x.name for x in typ)
    return lambda arg: _strings.instance_from_string(typ, arg), InstantiatorMetadata(
        nargs=None,
        metavar=typ.__name__.upper(),
        choices=auto_choices,
        is_optional=False,
    )


def _instantiator_from_container_type(
    typ: Type, type_from_typevar: Dict[TypeVar, Type]
) -> Optional[Tuple[Instantiator, InstantiatorMetadata]]:
    """Attempt to create an instantiator from a container type. Returns `None` is no
    container type is found."""

    type_origin = get_origin(typ)
    if type_origin is None:
        return None

    # Unwrap Final types.
    if type_origin is Final:
        (contained_type,) = get_args(typ)
        return instantiator_from_type(contained_type, type_from_typevar)

    # Unwrap Annotated types.
    if hasattr(typ, "__class__") and typ.__class__ == _AnnotatedAlias:
        return instantiator_from_type(type_origin, type_from_typevar)

    # List, tuples, and sequences.
    if type_origin in (
        collections.abc.Sequence,  # different from typing.Sequence!
        list,  # different from typing.List!
        set,  # different from typing.Set!
    ):
        (contained_type,) = get_args(typ)
        container_type = type_origin
        if container_type is collections.abc.Sequence:
            container_type = list

        make, inner_meta = _instantiator_from_type_inner(
            contained_type, type_from_typevar
        )
        return lambda strings: container_type(
            [make(x) for x in strings]
        ), InstantiatorMetadata(
            nargs="+",
            metavar=inner_meta.metavar,
            choices=inner_meta.choices,
            is_optional=False,
        )

    # Tuples.
    if type_origin is tuple:
        types = get_args(typ)
        typeset = set(types)  # Note that sets are unordered.
        typeset_no_ellipsis = typeset - {Ellipsis}  # type: ignore

        if typeset_no_ellipsis != typeset:
            # Ellipsis: variable argument counts.
            if len(typeset_no_ellipsis) > 1:
                raise UnsupportedTypeAnnotationError(
                    "When an ellipsis is used, tuples must contain only one type."
                )
            (contained_type,) = typeset_no_ellipsis

            make, inner_meta = _instantiator_from_type_inner(
                contained_type, type_from_typevar
            )
            return lambda strings: tuple(
                [make(x) for x in strings]
            ), InstantiatorMetadata(
                nargs="+",
                metavar=inner_meta.metavar,
                choices=inner_meta.choices,
                is_optional=False,
            )

        else:
            instantiators, metas = zip(
                *map(
                    lambda t: _instantiator_from_type_inner(t, type_from_typevar),
                    types,
                )
            )
            if len(set(m.choices for m in metas)) > 1:
                raise UnsupportedTypeAnnotationError(
                    "Due to constraints in argparse, all choices in fixed-length tuples"
                    " must match. This restricts mixing enums & literals with other"
                    " types."
                )
            return lambda strings: tuple(
                make(x) for make, x in zip(instantiators, strings)
            ), InstantiatorMetadata(
                nargs=len(types),
                metavar=tuple(m.metavar for m in metas),
                choices=metas[0].choices,
                is_optional=False,
            )

    # Optionals.
    if type_origin is Union:
        options = set(get_args(typ))
        assert (
            len(options) == 2 and type(None) in options
        ), "Union must be either over dataclasses (for subparsers) or Optional"
        (typ,) = options - {type(None)}
        instantiator, metadata = _instantiator_from_type_inner(
            typ, type_from_typevar, allow_sequences=True
        )
        return instantiator, dataclasses.replace(metadata, is_optional=True)

    # Literals.
    if type_origin is Literal:
        choices = get_args(typ)
        contained_type = type(next(iter(choices)))
        assert all(
            map(lambda c: type(c) == contained_type, choices)
        ), "All choices in literal must have the same type!"
        if issubclass(contained_type, enum.Enum):
            choices = tuple(map(lambda x: x.name, choices))
        instantiator, metadata = _instantiator_from_type_inner(
            contained_type, type_from_typevar
        )
        assert (
            # Choices provided by the contained type
            metadata.choices is None
            or len(set(choices) - set(metadata.choices)) == 0
        )
        return instantiator, dataclasses.replace(metadata, choices=choices)

    return None


def _instantiator_from_type_inner(
    typ: Type,
    type_from_typevar: Dict[TypeVar, Type],
    allow_sequences: bool = False,
    allow_optional: bool = False,
) -> Tuple[Instantiator, InstantiatorMetadata]:
    """Thin wrapper over instantiator_from_type, with some extra asserts for catching
    errors."""
    out = instantiator_from_type(typ, type_from_typevar)
    if not allow_sequences and out[1].nargs is not None:
        raise UnsupportedTypeAnnotationError("Nested sequence types are not supported!")
    if not allow_optional and out[1].is_optional:
        raise UnsupportedTypeAnnotationError("Nested optional types are not supported!")
    return out
