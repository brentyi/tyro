from __future__ import annotations

from typing import Any, Dict, Optional

from tyro.constructors._registry import check_default_instances_context
from tyro.constructors._struct_spec import (
    InvalidDefaultInstanceError,
    UnsupportedStructTypeMessage,
)

from . import _fields, _singleton
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

    # Get first subcommand that doesn't throw an error in strict mode.
    for subcommand_name, subcommand_type in subcommand_type_from_name.items():
        # We could also use typeguard here, but for now (November 19, 2024)
        # our own implementation has better support for nested generics.

        # try:
        #     import typeguard
        #
        #     typeguard.check_type(default, subcommand_type)
        #     return subcommand_name
        # except typeguard.TypeCheckError:
        #     continue

        if _recursive_struct_match(subcommand_type, default, root=True):
            return subcommand_name

    # Failed. This should never happen, we'll raise an error outside of this function if
    # this is the case.
    return None  # pragma: no cover


def _recursive_struct_match(subcommand_type: Any, default: Any, root: bool) -> bool:
    """Returns `True` if the given type and default instance are compatible
    with each other."""
    # Can we generate a field list from this type?
    try:
        with check_default_instances_context():
            field_list = _fields.field_list_from_type_or_callable(
                subcommand_type, default, support_single_arg_types=root
            )
    except InvalidDefaultInstanceError:
        # Found a struct type that matches, but the default instance isn't
        # compatible.
        return False

    # Base case: found a leaf.
    if isinstance(field_list, UnsupportedStructTypeMessage):
        return True

    for field in field_list[1]:
        if not _recursive_struct_match(field.type, field.default, root=False):
            return False

    return True
