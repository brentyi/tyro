"""Experimental features and options for tyro.

This module contains experimental features that may change or be removed in future versions.
Use with caution in production code.
"""

from __future__ import annotations

import os
from typing import Any, Literal

from typing_extensions import TypedDict


class OptionsDict(TypedDict):
    """Options for experimental tyro features.

    Attributes:
        enable_timing: Enable timing output for performance benchmarking.
        backend: Backend to use for parsing ("argparse" or "tyro").
    """

    enable_timing: bool
    backend: Literal["argparse", "tyro"]


def read_option(str_name: str, typ: Any, default: Any) -> Any:  # pragma: no cover
    if str_name in os.environ:
        from .constructors import (
            ConstructorRegistry,
            PrimitiveTypeInfo,
            UnsupportedTypeAnnotationError,
        )

        spec = ConstructorRegistry.get_primitive_spec(
            PrimitiveTypeInfo.make(typ, set())
        )
        assert not isinstance(spec, UnsupportedTypeAnnotationError)
        value = os.environ[str_name]
        if spec.choices is not None:
            assert value in spec.choices, (
                f"{str_name}={value} not in choices {spec.choices}"
            )
        return spec.instance_from_str([value])
    return default


# Global options dictionary.
options: OptionsDict = {
    "enable_timing": read_option("PYTHON_TYRO_ENABLE_TIMING", bool, False),
    "backend": read_option("PYTHON_TYRO_BACKEND", Literal["argparse", "tyro"], "tyro"),
}
