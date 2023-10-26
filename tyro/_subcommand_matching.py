from __future__ import annotations

import dataclasses
from typing import Any, Callable, Dict, Optional, Tuple, Union

from typing_extensions import get_args, get_origin

from . import _fields, _instantiators, _resolver, _typing
from .conf import _confstruct


def match_subcommand(
    default: Any,
    subcommand_config_from_name: Dict[str, _confstruct._SubcommandConfiguration],
    subcommand_type_from_name: Dict[str, type],
) -> Optional[str]:
    """Given a subcommand mapping and a default, return which subcommand the default
    corresponds to."""

    # It's really hard to concretize a generic type at runtime, so we just...
    # don't. :-)
    if hasattr(type(default), "__parameters__"):
        raise _instantiators.UnsupportedTypeAnnotationError(
            "Default values for generic subparsers are not supported."
        )

    # Get default subcommand name: by default hash.
    default_hash = object.__hash__(default)
    for subcommand_name, conf in subcommand_config_from_name.items():
        if conf.default in _fields.MISSING_SINGLETONS:
            continue
        if default_hash == object.__hash__(conf.default):
            return subcommand_name

    # Get default subcommand name: by default value.
    for subcommand_name, conf in subcommand_config_from_name.items():
        if conf.default in _fields.MISSING_SINGLETONS:
            continue
        equal = default == conf.default
        if isinstance(equal, bool) and equal:
            return subcommand_name

    # Get default subcommand name: by concrete type tree.
    typetree = _TypeTree.make(type(default), default)
    for subcommand_name, conf in subcommand_config_from_name.items():
        if conf.default in _fields.MISSING_SINGLETONS:
            continue
        if typetree == _TypeTree.make(type(conf.default), conf.default):
            return subcommand_name

    # Get default subcommand name: by annotated type tree.
    for subcommand_name, subcommand_type in subcommand_type_from_name.items():
        if typetree.is_subtype_of(
            _TypeTree.make(subcommand_type, _fields.MISSING_NONPROP)
        ):
            return subcommand_name

    # Failed!
    return None


@dataclasses.dataclass(frozen=True)
class _TypeTree:
    typ: Any
    children: Dict[str, _TypeTree]

    @staticmethod
    def make(
        typ: Union[Callable, _typing.TypeForm],
        default_instance: _fields.DefaultInstance,
    ) -> _TypeTree:
        """From an object instance, return a data structure representing the types in the object."""
        try:
            typ, _type_from_typevar, field_list = _fields.field_list_from_callable(
                typ, default_instance=default_instance
            )
        except _instantiators.UnsupportedTypeAnnotationError:
            return _TypeTree(typ, {})

        return _TypeTree(
            typ,
            {
                field.name: _TypeTree.make(field.type_or_callable, field.default)
                for field in field_list
            },
        )

    def is_subtype_of(self, supertype: _TypeTree) -> bool:
        # Generalize to unions.
        def _get_type_options(typ: _typing.TypeForm) -> Tuple[_typing.TypeForm, ...]:
            return get_args(typ) if get_origin(typ) is Union else (typ,)

        self_types = _get_type_options(self.typ)
        super_types = _get_type_options(supertype.typ)

        # Check against supertypes.
        for self_type in self_types:
            self_type = _resolver.unwrap_annotated(self_type)[0]
            ok = False
            for super_type in super_types:
                super_type = _resolver.unwrap_annotated(super_type)[0]
                if issubclass(self_type, super_type):
                    ok = True
            if not ok:
                return False

        return True
