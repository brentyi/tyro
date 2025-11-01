"""Unit test for narrow_subtypes_NEW() to validate TyroType optimization."""

from dataclasses import dataclass
from typing import Union

from src.tyro._resolver import narrow_subtypes_NEW
from src.tyro._singleton import MISSING_NONPROP
from src.tyro._tyro_type import TyroType, type_to_tyro_type


@dataclass
class Animal:
    name: str


@dataclass
class Cat(Animal):
    meow: bool = True


def test_narrow_subtypes_NEW_basic():
    """Test basic type narrowing from superclass to subclass."""
    # Create TyroType for Animal
    animal_type = type_to_tyro_type(Animal)

    # Provide a Cat instance as default
    cat_instance = Cat(name="Fluffy")

    # Should narrow to Cat
    narrowed = narrow_subtypes_NEW(animal_type, cat_instance)

    assert narrowed.type_origin == Cat
    print(f"✅ Basic narrowing: Animal -> Cat")


def test_narrow_subtypes_NEW_no_default():
    """Test that no narrowing happens without a default."""
    animal_type = type_to_tyro_type(Animal)

    # No default provided
    narrowed = narrow_subtypes_NEW(animal_type, MISSING_NONPROP)

    assert narrowed.type_origin == Animal
    print(f"✅ No narrowing without default")


def test_narrow_subtypes_NEW_preserves_annotations():
    """Test that annotations are preserved during narrowing."""
    from typing_extensions import Annotated

    # Create annotated type
    annotated_animal = Annotated[Animal, "some_metadata"]
    animal_type = type_to_tyro_type(annotated_animal)

    # Narrow with Cat instance
    cat_instance = Cat(name="Fluffy")
    narrowed = narrow_subtypes_NEW(animal_type, cat_instance)

    assert narrowed.type_origin == Cat
    assert narrowed.annotations == ("some_metadata",)
    print(f"✅ Annotations preserved: {narrowed.annotations}")


def test_narrow_subtypes_NEW_union():
    """Test that Union types are not narrowed."""
    # Create TyroType for Union[Animal, str]
    union_type = type_to_tyro_type(Union[Animal, str])

    # Provide Cat instance
    cat_instance = Cat(name="Fluffy")

    # Should NOT narrow (unions are handled differently)
    narrowed = narrow_subtypes_NEW(union_type, cat_instance)

    # Should return the same union type
    assert narrowed.type_origin == Union
    print(f"✅ Union types not narrowed")


def test_narrow_subtypes_NEW_no_reconstruction():
    """Verify that narrow_subtypes_NEW doesn't call reconstruct_type_from_tyro_type."""
    # This is the KEY test - we want to ensure no reconstruction happens.
    # We can't easily assert this directly, but we can check the function doesn't
    # import or use reconstruct_type_from_tyro_type.

    import inspect
    source = inspect.getsource(narrow_subtypes_NEW)

    assert "reconstruct_type_from_tyro_type" not in source
    print(f"✅ No reconstruction in narrow_subtypes_NEW!")


if __name__ == "__main__":
    print("Testing narrow_subtypes_NEW()...\n")

    test_narrow_subtypes_NEW_basic()
    test_narrow_subtypes_NEW_no_default()
    test_narrow_subtypes_NEW_preserves_annotations()
    test_narrow_subtypes_NEW_union()
    test_narrow_subtypes_NEW_no_reconstruction()

    print("\n✅ All tests passed!")
