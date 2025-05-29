"""Tests for LazyAnnotation functionality."""

from __future__ import annotations

from typing_extensions import Annotated

import tyro


def test_lazy_annotation_basic():
    """Test basic LazyAnnotation functionality with dynamic choices."""
    # Global state to simulate a registry that changes over time.
    registry: dict[str, str] = {}

    def register_item(name: str, value: str) -> None:
        """Register an item in our test registry."""
        registry[name] = value

    def get_registered_items() -> list[str]:
        """Get all registered item names."""
        return list(registry.keys())

    def is_registered(name: str) -> bool:
        """Check if an item is registered."""
        return name in registry

    # Start with an empty registry.
    registry.clear()

    # Register some initial items.
    register_item("item1", "value1")
    register_item("item2", "value2")

    # Use a string annotation instead of a type alias to avoid namespace issues.
    def main(
        item: Annotated[
            str,
            tyro.LazyAnnotation(
                lambda: tyro.constructors.PrimitiveConstructorSpec(
                    nargs=1,
                    metavar="{" + ",".join(get_registered_items()[:2]) + ",...}",
                    instance_from_str=lambda args: args[0],
                    is_instance=lambda instance: isinstance(instance, str)
                    and is_registered(instance),
                    str_from_instance=lambda instance: [instance],
                    choices=tuple(get_registered_items()),
                )
            ),
        ]
    ) -> str:
        return item

    # Test that initially registered items work.
    assert tyro.cli(main, args=["--item", "item1"]) == "item1"
    assert tyro.cli(main, args=["--item", "item2"]) == "item2"

    # Add a new item to the registry after the type was defined.
    register_item("item3", "value3")

    # The lazy annotation should pick up the new item.
    assert tyro.cli(main, args=["--item", "item3"]) == "item3"

    # Test that invalid choices are rejected.
    try:
        tyro.cli(main, args=["--item", "invalid"])
        assert False, "Should have raised an error for invalid choice"
    except SystemExit:
        pass  # Expected behavior for invalid choice.


def test_lazy_annotation_with_nested_annotations():
    """Test LazyAnnotation working with other annotations like tyro.conf.arg."""
    registry: dict[str, str] = {}

    def register_item(name: str, value: str) -> None:
        registry[name] = value

    def get_registered_items() -> list[str]:
        return list(registry.keys())

    def is_registered(name: str) -> bool:
        return name in registry

    registry.clear()
    register_item("model1", "value1")
    register_item("model2", "value2")

    def main(
        model: Annotated[
            str,
            tyro.LazyAnnotation(
                lambda: tyro.constructors.PrimitiveConstructorSpec(
                    nargs=1,
                    metavar="{" + ",".join(get_registered_items()[:2]) + ",...}",
                    instance_from_str=lambda args: args[0],
                    is_instance=lambda instance: isinstance(instance, str)
                    and is_registered(instance),
                    str_from_instance=lambda instance: [instance],
                    choices=tuple(get_registered_items()),
                )
            ),
            tyro.conf.arg(help="Model to use for processing"),
        ]
    ) -> str:
        return model

    # Verify it works with the additional annotation.
    assert tyro.cli(main, args=["--model", "model1"]) == "model1"

    # Add a new model and verify it's available.
    register_item("model3", "value3")
    assert tyro.cli(main, args=["--model", "model3"]) == "model3"


def test_lazy_annotation_evaluation_timing():
    """Test that LazyAnnotation evaluation happens at the right time."""
    registry: dict[str, str] = {}

    def register_item(name: str, value: str) -> None:
        registry[name] = value

    def get_registered_items() -> list[str]:
        return list(registry.keys())

    registry.clear()

    # Track when the constructor is called.
    call_count = 0

    def lazy_constructor():
        nonlocal call_count
        call_count += 1
        return tyro.constructors.PrimitiveConstructorSpec(
            nargs=1,
            metavar="VALUE",
            instance_from_str=lambda args: args[0],
            is_instance=lambda instance: isinstance(instance, str),
            str_from_instance=lambda instance: [instance],
            choices=tuple(get_registered_items()),
        )

    def main(
        value: Annotated[str, tyro.LazyAnnotation(lazy_constructor)]
    ) -> str:
        return value

    # The constructor should not have been called yet.
    assert call_count == 0

    # Register an item.
    register_item("test", "value")

    # Now call tyro.cli, which should trigger the lazy evaluation.
    result = tyro.cli(main, args=["--value", "test"])
    assert result == "test"

    # The constructor should have been called exactly once.
    assert call_count == 1

    # Running again should call the constructor again (it's not cached).
    tyro.cli(main, args=["--value", "test"])
    assert call_count == 2


def test_lazy_annotation_error_handling():
    """Test error handling when LazyAnnotation constructor fails."""

    def failing_constructor():
        raise ValueError("Constructor failed!")

    def main(
        value: Annotated[str, tyro.LazyAnnotation(failing_constructor)]
    ) -> str:
        return value

    # This should raise the error from the constructor.
    try:
        tyro.cli(main, args=["--value", "test"])
        assert False, "Should have raised an error"
    except ValueError as e:
        assert str(e) == "Constructor failed!"


def test_lazy_annotation_non_primitive_constructor_spec():
    """Test LazyAnnotation with constructor that returns non-PrimitiveConstructorSpec."""

    def constructor_returning_other_annotation():
        # Return a nested annotation rather than a PrimitiveConstructorSpec directly.
        return Annotated[
            str,
            tyro.constructors.PrimitiveConstructorSpec(
                nargs=1,
                metavar="NESTED",
                instance_from_str=lambda args: args[0],
                is_instance=lambda instance: isinstance(instance, str),
                str_from_instance=lambda instance: [instance],
            ),
        ]

    def main(
        value: Annotated[str, tyro.LazyAnnotation(constructor_returning_other_annotation)]
    ) -> str:
        return value

    # This should work by extracting the PrimitiveConstructorSpec from the nested annotation.
    result = tyro.cli(main, args=["--value", "test"])
    assert result == "test"