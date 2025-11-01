"""TyroType infrastructure for efficient type manipulation without reconstruction."""

from __future__ import annotations

import dataclasses
from typing import Any, Literal, Union, cast, get_args, get_origin

from typing_extensions import Annotated

from ._typing import TypeForm


@dataclasses.dataclass(frozen=True)
class TyroType:
    """Internal representation of types that avoids expensive reconstruction.

    Instead of creating new type objects (e.g., Union[int, str]), we store the
    components separately and only reconstruct when absolutely necessary.
    """

    type_origin: Any  # The base type (int, list, Union, etc.). We use `Any` because `Union` is not a "type".
    args: tuple[Union[TyroType, Any], ...]  # Can contain TyroTypes or literals
    annotations: tuple[Any, ...]  # Annotations from Annotated types

    def __repr__(self) -> str:
        """Create a readable representation of the TyroType."""
        if self.annotations:
            return f"TyroType(origin={self.type_origin}, args={self.args}, annotations={self.annotations})"
        else:
            return f"TyroType(origin={self.type_origin}, args={self.args})"


def type_to_tyro_type(typ: TypeForm[Any]) -> TyroType:
    """Convert a Python type to our internal TyroType representation.

    This function recursively converts types and their arguments to TyroType,
    extracting annotations from Annotated types.
    """
    # Handle Annotated types specially to extract annotations
    annotations: tuple[Any, ...] = ()
    origin = get_origin(typ)

    if origin is Annotated:
        args = get_args(typ)
        if args:
            # First arg is the actual type, rest are annotations
            typ = args[0]
            annotations = args[1:]
            origin = get_origin(typ)

    # Get the type origin and args
    if origin is not None:
        type_origin = origin
        args = get_args(typ)
    else:
        # Base type like int, str, etc.
        type_origin = typ
        args = ()

    # Recursively convert args to TyroType
    converted_args: list[Union[TyroType, Any]] = []
    for arg in args:
        # Check if arg is a type (not a literal value)
        # Literal values include: ints, strings, None, etc.
        # Types include: classes, generic aliases
        if isinstance(arg, type) or hasattr(arg, "__origin__") or arg is None or arg is type(None):
            # It's a type (including None/NoneType), convert it recursively
            if arg is None:
                arg = type(None)  # Normalize None to NoneType
            converted_args.append(type_to_tyro_type(arg))
        else:
            # It's a literal value (e.g., in Literal[1, 2, 3])
            converted_args.append(arg)

    return TyroType(
        type_origin=type_origin,
        args=tuple(converted_args),
        annotations=annotations
    )


def reconstruct_type_from_tyro_type(tyro: TyroType) -> TypeForm[Any]:
    """Convert a TyroType back to a Python type.

    This is the expensive operation we're trying to minimize, but it's needed
    for compatibility with existing code.
    """
    # Reconstruct args first
    reconstructed_args: list[Any] = []
    for arg in tyro.args:
        if isinstance(arg, TyroType):
            reconstructed_args.append(reconstruct_type_from_tyro_type(arg))
        else:
            # Literal value
            reconstructed_args.append(arg)

    # Reconstruct the type
    if reconstructed_args:
        # Generic type with args
        if tyro.type_origin is Union:
            # Special handling for Union
            from typing import Union as UnionType
            result = UnionType[tuple(reconstructed_args)]
        elif tyro.type_origin is Literal:
            # Special handling for Literal
            result = Literal[tuple(reconstructed_args)]
        else:
            # For other origins (list, dict, tuple, etc.)
            # Try to use the origin's subscript method
            try:
                if len(reconstructed_args) == 1:
                    result = tyro.type_origin[reconstructed_args[0]]
                else:
                    result = tyro.type_origin[tuple(reconstructed_args)]
            except (TypeError, AttributeError):
                # If subscripting fails, return the origin
                result = tyro.type_origin
    else:
        # Simple type without args
        result = tyro.type_origin

    # Add annotations if present
    if tyro.annotations:
        result = Annotated[(result,) + tyro.annotations]

    return cast(TypeForm[Any], result)


def tyro_type_from_origin_args(
    origin: Any,
    args: tuple[Union[TyroType, Any], ...],
    annotations: tuple[Any, ...] = ()
) -> TyroType:
    """Helper to create a TyroType from origin, args, and annotations.

    This is useful when modifying existing TyroTypes.
    """
    return TyroType(
        type_origin=origin,
        args=args,
        annotations=annotations
    )