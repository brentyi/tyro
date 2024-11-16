from __future__ import annotations

import dataclasses
from typing import Any, Callable, Dict, Optional, Tuple, Union

from typing_extensions import get_args, get_origin

from tyro.constructors._struct_spec import UnsupportedStructTypeMessage

from . import _fields, _resolver, _singleton, _typing
from .conf import _confstruct


def match_subcommand(
    default: Any,
    subcommand_config_from_name: Dict[str, _confstruct._SubcommandConfig],
    subcommand_type_from_name: Dict[str, type],
) -> Optional[str]:
    """Given a subcommand mapping and a default, return which subcommand the default
    corresponds to.

    TOOD: this function is based on heuristics. While it should be robust to
    most real-world scenarios, there's room for improvement for generic types.
    """

    # Get default subcommand name: by default hash.
    default_hash = object.__hash__(default)
    for subcommand_name, conf in subcommand_config_from_name.items():
        if conf.default in _singleton.MISSING_AND_MISSING_NONPROP:
            continue
        if default_hash == object.__hash__(conf.default):
            return subcommand_name

    # Get default subcommand name: by default value.
    for subcommand_name, conf in subcommand_config_from_name.items():
        if conf.default in _singleton.MISSING_AND_MISSING_NONPROP:
            continue
        equal = default == conf.default
        if isinstance(equal, bool) and equal:
            return subcommand_name

    # Get default subcommand name: by concrete type tree.
    typetree = _TypeTree.make(type(default), default)
    for subcommand_name, conf in subcommand_config_from_name.items():
        if conf.default in _singleton.MISSING_AND_MISSING_NONPROP:
            continue
        if typetree == _TypeTree.make(type(conf.default), conf.default):
            return subcommand_name

    # Get default subcommand name: by annotated type tree.
    typetree_from_name = {
        subcommand_name: _TypeTree.make(subcommand_type, _singleton.MISSING_NONPROP)
        for subcommand_name, subcommand_type in subcommand_type_from_name.items()
    }
    for subcommand_name in subcommand_type_from_name.keys():
        # Equality check for type tree.
        if typetree == typetree_from_name[subcommand_name]:
            return subcommand_name
    for subcommand_name in subcommand_type_from_name.keys():
        # Leaky subtype check.
        if typetree.is_subtype_of(typetree_from_name[subcommand_name]):
            return subcommand_name

    # Failed. This should never happen, we'll raise an error outside of this function if
    # this is the case.
    return None  # pragma: no cover


@dataclasses.dataclass(frozen=True)
class _TypeTree:
    typ: Any
    children: Dict[str, _TypeTree]

    @staticmethod
    def make(
        typ: Union[Callable, _typing.TypeForm],
        default_instance: Any,
    ) -> _TypeTree:
        """From an object instance, return a data structure representing the types in the object."""

        typ_unwrap = _resolver.resolve_generic_types(typ)[0]

        field_list_out = _fields.field_list_from_type_or_callable(
            typ, default_instance=default_instance, support_single_arg_types=False
        )
        if isinstance(field_list_out, UnsupportedStructTypeMessage):
            return _TypeTree(typ_unwrap, {})

        typ, field_list = field_list_out
        return _TypeTree(
            typ_unwrap,
            {
                field.intern_name: _TypeTree.make(field.type_stripped, field.default)
                for field in field_list
            },
        )

    def is_subtype_of(self, supertype: _TypeTree) -> bool:
        """Best-effort subcommand matching."""

        # Generalize to unions.
        def _get_type_options(typ: _typing.TypeForm) -> Tuple[_typing.TypeForm, ...]:
            return get_args(typ) if get_origin(typ) is Union else (typ,)

        self_types = _get_type_options(self.typ)
        super_types = _get_type_options(supertype.typ)

        # Check against supertypes. TODO: the heuristics below could be more
        # principled. We should revisit.
        for self_type in self_types:
            self_type = _resolver.unwrap_annotated(self_type)
            ok = False
            for super_type in super_types:
                super_type = _resolver.unwrap_annotated(super_type)
                try:
                    if issubclass(self_type, super_type):
                        ok = True
                except TypeError:
                    pass
            if not ok:
                return False

        for child_name, child in self.children.items():
            if child_name not in supertype.children or not child.is_subtype_of(
                supertype.children[child_name]
            ):
                return False

        return True
