import types
import typing
from typing import Any

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


def is_typing_literal(obj: Any) -> bool:
    return obj in LiteralTypes


def is_typing_union(obj: Any) -> bool:
    return obj in UnionTypes


def is_typing_final(obj: Any) -> bool:
    return obj in FinalTypes


def is_typing_readonly(obj: Any) -> bool:
    return obj in ReadOnlyTypes


def is_typing_annotated(obj: Any) -> bool:
    return obj in AnnotatedTypes


def is_typing_generic(obj: Any) -> bool:
    return obj in GenericTypes


def is_typing_protocol(obj: Any) -> bool:
    return obj in ProtocolTypes


def is_typing_required(obj: Any) -> bool:
    return obj in RequiredTypes


def is_typing_notrequired(obj: Any) -> bool:
    return obj in NotRequiredTypes


def is_typing_classvar(obj: Any) -> bool:
    return obj in ClassVarTypes


def is_typing_typealiastype(obj: Any) -> bool:
    return obj in TypeAliasTypes
