#!/usr/bin/env python3
"""Quick test of LazyAnnotation functionality."""

import os
import sys

# Add the src directory to Python path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from typing_extensions import Annotated

import tyro

# Simulate a registry system.
model_registry: dict[str, str] = {}


def register_model(name: str, model: str) -> None:
    """Register a model in our test registry."""
    if name not in model_registry:
        model_registry[name] = model


def registered_models() -> list[str]:
    """Get all registered model names."""
    return list(model_registry.keys())


def is_registered(name: str) -> bool:
    """Check if a model name is registered."""
    return name in model_registry


# Register some initial models.
register_model("model1", "TestModel1")

# Define ModelName using LazyAnnotation.
ModelName = Annotated[
    str,
    tyro.LazyAnnotation(
        lambda: tyro.constructors.PrimitiveConstructorSpec(
            nargs=1,
            metavar="{" + ",".join(registered_models()[:3]) + ",...}",
            instance_from_str=lambda args: args[0],
            is_instance=lambda instance: isinstance(instance, str)
            and is_registered(instance),
            str_from_instance=lambda instance: [instance],
            choices=tuple(registered_models()),
        )
    ),
    tyro.conf.arg(
        help_behavior_hint=lambda df: f"(default: {df}, run script to see models)"
    ),
]

# Register a second model after ModelName type was defined.
register_model("model2", "TestModel2")


def main(model: ModelName) -> None:
    """Test function that takes a model name."""
    print(f"Selected model: {model}")
    print(f"Model info: {model_registry[model]}")


if __name__ == "__main__":
    tyro.cli(main)
