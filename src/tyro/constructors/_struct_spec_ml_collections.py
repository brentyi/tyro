from __future__ import annotations

import copy
import sys
from typing import Any

from typing_extensions import Annotated

from .._resolver import narrow_collection_types
from .._singleton import EXCLUDE_FROM_CALL
from ..conf import _confstruct
from ._struct_spec import StructConstructorSpec, StructFieldSpec, StructTypeInfo

_NotRootConfigDict = None  # type: ignore


def ml_collections_rule(info: StructTypeInfo) -> StructConstructorSpec | None:
    if "ml_collections" not in sys.modules.keys():  # pragma: no cover
        return None

    from ml_collections import FieldReference, config_dict

    # Lazy class definition.
    global _NotRootConfigDict
    if _NotRootConfigDict is None:

        class _NotRootConfigDict(config_dict.ConfigDict): ...

    if info.type not in (
        config_dict.ConfigDict,
        config_dict.FrozenConfigDict,
        _NotRootConfigDict,
    ):
        return None

    # Handling ml_collections.ConfigDict is mostly very easy. The one
    # complication is the FieldReference type.
    #
    # To make handling this easier, we'll just ignore FieldReferences everywhere
    # except for the "root" ConfigDict object.
    #
    # To track this, we'll internally convert structures that look like:
    # - root: ConfigDict
    # -  key1: ConfigDict
    # -  key2: ConfigDict
    # -  key3: int
    #
    # Into:
    # - root: ConfigDict
    # -  key1: NotRootConfigDict
    # -  key2: NotRootConfigDict
    # -  key3: int
    #
    def _instantiate(**kwargs):
        if info.type is config_dict.ConfigDict:
            # Root. `.update()` should track all of the field references.
            config = copy.deepcopy(info.default)
            config.update(kwargs)
            return config
        elif info.type is config_dict.FrozenConfigDict:
            # Make mutable, update, then freeze.
            config = copy.deepcopy(config_dict.ConfigDict(info.default))
            config.update(kwargs)
            return config_dict.FrozenConfigDict(config)
        else:
            # Not root. Just return the kwargs.
            return config_dict.ConfigDict(kwargs)

    # For creating individual fields, we're going to do two things...
    def _make_field_spec(k: str, v: Any) -> StructFieldSpec:
        val_type = narrow_collection_types(info.default.get_type(k), v)
        # (1) Convert all ConfigDict types to NotRootConfigDict.
        if val_type in (config_dict.ConfigDict, config_dict.FrozenConfigDict):
            val_type = _NotRootConfigDict
            v = _NotRootConfigDict(v)
        # (2) Exclude FieldReferences from the call signature by default. This will
        # only include a field reference in the kwargs if a value is explicitly
        # passed in.
        elif isinstance(v, FieldReference):
            v = v.get()
            val_type = narrow_collection_types(type(v), v)
            val_type = Annotated[
                val_type,
                _confstruct.arg(
                    help=f"Reference default: {v}.",
                    help_behavior_hint="(assigns reference)",
                ),
            ]
            v = EXCLUDE_FROM_CALL

        return StructFieldSpec(k, val_type, v)  # type: ignore

    return StructConstructorSpec(
        instantiate=_instantiate,
        fields=tuple(
            _make_field_spec(k, v)
            for k, v in info.default.items(preserve_field_references=True)
        ),
    )
