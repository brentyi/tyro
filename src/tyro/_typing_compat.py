import types
import typing
from typing import Any, Set

import typing_extensions

LiteralTypes = {typing.Literal, typing_extensions.Literal}
UnionTypes = {
    typing.Union,
    typing_extensions.Union,
    getattr(types, "UnionType", typing.Union),
}
FinalTypes = {typing.Final, typing_extensions.Final}
ReadOnlyTypes = {
    getattr(typing, "ReadOnly", typing_extensions.ReadOnly),
    typing_extensions.ReadOnly,
}
AnnotatedTypes = {
    getattr(typing, "Annotated", typing_extensions.Annotated),
    typing_extensions.Annotated,
}
GenericTypes = {typing.Generic, typing_extensions.Generic}
ProtocolTypes = {typing.Protocol, typing_extensions.Protocol}
RequiredTypes = {
    getattr(typing, "Required", typing_extensions.Required),
    typing_extensions.Required,
}
NotRequiredTypes = {
    getattr(typing, "NotRequired", typing_extensions.NotRequired),
    typing_extensions.NotRequired,
}
ClassVarTypes = {
    getattr(typing, "ClassVar", typing_extensions.ClassVar),
    typing_extensions.ClassVar,
}
TypeAliasTypes = {
    getattr(typing, "TypeAliasType", typing_extensions.TypeAliasType),
    typing_extensions.TypeAliasType,
}
UnpackTypes = {
    getattr(typing, "Unpack", typing_extensions.Unpack),
    typing_extensions.Unpack,
}


def _is_any_of(obj: Any, types: Set[Any]) -> bool:
    try:
        return obj in types
    except TypeError:
        # Not hashable. For example: Annotated[] types with unhashable metadata.
        return False


def is_typing_literal(obj: Any) -> bool:
    return _is_any_of(obj, LiteralTypes)


def is_typing_union(obj: Any) -> bool:
    return _is_any_of(obj, UnionTypes)


def is_typing_final(obj: Any) -> bool:
    return _is_any_of(obj, FinalTypes)


def is_typing_readonly(obj: Any) -> bool:
    return _is_any_of(obj, ReadOnlyTypes)


def is_typing_annotated(obj: Any) -> bool:
    return _is_any_of(obj, AnnotatedTypes)


def is_typing_generic(obj: Any) -> bool:
    return _is_any_of(obj, GenericTypes)


def is_typing_protocol(obj: Any) -> bool:
    return _is_any_of(obj, ProtocolTypes)


def is_typing_required(obj: Any) -> bool:
    return _is_any_of(obj, RequiredTypes)


def is_typing_notrequired(obj: Any) -> bool:
    return _is_any_of(obj, NotRequiredTypes)


def is_typing_classvar(obj: Any) -> bool:
    return _is_any_of(obj, ClassVarTypes)


def is_typing_typealiastype(obj: Any) -> bool:
    return _is_any_of(obj, TypeAliasTypes)


def is_typing_unpack(obj: Any) -> bool:
    return _is_any_of(obj, UnpackTypes)
