from __future__ import annotations

import sys
from typing import Any, Tuple, Type


def is_flax_module(cls: Type[Any]) -> Tuple[bool, Tuple[str, ...]]:
    """Check if a class is a Flax module and return fields to skip.

    Returns:
        Tuple of (is_flax_module, fields_to_skip)
    """
    # Skip non-dataclasses
    if not is_dataclass_type(cls):
        return False, ()

    # Check if dataclass is a flax module. This is only possible if flax is already
    # loaded.
    #
    # We generally want to avoid importing flax, since it requires a lot of heavy
    # imports.
    if "flax.linen" in sys.modules.keys():
        try:
            import flax.linen

            if issubclass(cls, flax.linen.Module):
                # For flax modules, we ignore the built-in "name" and "parent" fields.
                return True, ("name", "parent")
        except ImportError:
            pass

    return False, ()


def is_dataclass_type(obj: Any) -> bool:
    """Check if an object is a dataclass type."""
    import dataclasses

    return isinstance(obj, type) and dataclasses.is_dataclass(obj)
