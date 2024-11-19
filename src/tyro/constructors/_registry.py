from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, ClassVar, Union

import typeguard
from typing_extensions import Literal

from tyro._singleton import DEFAULT_SENTINEL_SINGLETONS

from ._primitive_spec import (
    PrimitiveConstructorSpec,
    PrimitiveTypeInfo,
    UnsupportedTypeAnnotationError,
    apply_default_primitive_rules,
)
from ._struct_spec import (
    InvalidDefaultInstanceError,
    StructConstructorSpec,
    StructTypeInfo,
    apply_default_struct_rules,
)

current_registry: ConstructorRegistry | None = None

PrimitiveSpecRule = Callable[[PrimitiveTypeInfo], Union[PrimitiveConstructorSpec, None]]
StructSpecRule = Callable[[StructTypeInfo], Union[StructConstructorSpec, None]]

_check_default_instances_flag: bool = False


def check_default_instances() -> bool:
    """Check whether we should be strict about checking that default types and
    instances match.

    This is usually `False`; tyro attempts to be somewhat lenient when
    inconsistent types are encounted. Strictness, however, is useful for
    matching annotated subcommands to default values.
    """
    return _check_default_instances_flag


@contextmanager
def check_default_instances_context():
    """Context for whether we should be strict about checking that default
    types and instances match.

    This is usually `False`; tyro attempts to be somewhat lenient when
    inconsistent types are encounted. Strictness, however, is useful for
    matching annotated subcommands to default values.
    """
    global _check_default_instances_flag
    old_value = _check_default_instances_flag
    _check_default_instances_flag = True
    try:
        yield
    finally:
        _check_default_instances_flag = old_value


class ConstructorRegistry:
    """Registry for rules that define how types are constructed from
    command-line arguments.

    The behavior of CLIs generated by tyro are based on two types of rules.

    *Primitive rules* should be a callable with the signature:
    ```python
    (type_info: PrimitiveTypeInfo) -> PrimitiveConstructorSpec | None
    ```
    where `None` is returned if the rule doesn't apply. Each primitive rule
    defines behavior for a type that can be instantiated from a single
    command-line argument.


    *Struct rules* should be a callable with the signature:
    ```python
    (type_info: StructTypeInfo) -> StructConstructorSpec | None
    ```
    where `None` is returned if the rule doesn't apply. Each struct rule
    defines behavior for a type that can be instantiated from multiple
    command-line arguments.


    To activate a registry, use it as a context manager. For example:

    ```python
    registry = ConstructorRegistry()

    with registry:
        tyro.cli(...)
    ```
    """

    _active_registry: ClassVar[ConstructorRegistry | None] = None
    _old_registry: ConstructorRegistry | None = None

    def __init__(self) -> None:
        self._default_primitive_rules: list[PrimitiveSpecRule] = []
        self._custom_primitive_rules: list[PrimitiveSpecRule] = []
        self._struct_rules: list[StructSpecRule] = []

        # Apply the default primitive-handling rules.
        apply_default_primitive_rules(self)
        apply_default_struct_rules(self)

    def primitive_rule(self, rule: PrimitiveSpecRule) -> PrimitiveSpecRule:
        """Define a rule for constructing a primitive type from a string. The
        most recently added rule will be applied first.

        Custom primitive rules will take precedence over both default primitive
        rules and struct rules
        """

        self._custom_primitive_rules.append(rule)
        return rule

    def _default_primitive_rule(self, rule: PrimitiveSpecRule) -> PrimitiveSpecRule:
        self._default_primitive_rules.append(rule)
        return rule

    def struct_rule(self, rule: StructSpecRule) -> StructSpecRule:
        """Define a rule for constructing a primitive type from a string. The
        most recently added rule will be applied first."""

        self._struct_rules.append(rule)
        return rule

    def get_primitive_spec(
        self,
        type_info: PrimitiveTypeInfo,
        rule_mode: Literal["default", "custom", "all"] = "all",
    ) -> PrimitiveConstructorSpec:
        """Get a constructor specification for a given type."""

        if type_info._primitive_spec is not None:
            return type_info._primitive_spec

        if rule_mode in ("custom", "all"):
            for spec_factory in self._custom_primitive_rules[::-1]:
                maybe_spec = spec_factory(type_info)
                if maybe_spec is not None:
                    return maybe_spec
        if rule_mode in ("default", "all"):
            for spec_factory in self._default_primitive_rules[::-1]:
                maybe_spec = spec_factory(type_info)
                if maybe_spec is not None:
                    return maybe_spec

        raise UnsupportedTypeAnnotationError(
            f"Unsupported type annotation: {type_info.type}"
        )

    def get_struct_spec(
        self, type_info: StructTypeInfo
    ) -> StructConstructorSpec | None:
        """Get a constructor specification for a given type. Returns `None` if
        unsuccessful."""

        if (
            check_default_instances()
            and type_info.default not in DEFAULT_SENTINEL_SINGLETONS
        ):
            try:
                typeguard.check_type(type_info.default, type_info.type)
            except (typeguard.TypeCheckError, TypeError):
                raise InvalidDefaultInstanceError(
                    f"Invalid default instance for type {type_info.type}: {type_info.default}"
                )

        for spec_factory in self._struct_rules[::-1]:
            maybe_spec = spec_factory(type_info)
            if maybe_spec is not None:
                return maybe_spec

        return None

    @classmethod
    def _get_active_registry(cls) -> ConstructorRegistry:
        """Get the active registry. Can be changed by using a
        PrimitiveConstructorRegistry object as a context."""
        if cls._active_registry is None:
            cls._active_registry = ConstructorRegistry()
        return cls._active_registry

    def __enter__(self) -> None:
        cls = self.__class__
        self._old_registry = cls._active_registry
        cls._active_registry = self

    def __exit__(self, *args: Any) -> None:
        cls = self.__class__
        cls._active_registry = self._old_registry
