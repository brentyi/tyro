from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Union

import numpy as np
import pytest
from helptext_utils import get_helptext_with_checks
from typing_extensions import Annotated, Literal, get_args

import tyro

json_constructor_spec = tyro.constructors.PrimitiveConstructorSpec(
    nargs=1,
    metavar="JSON",
    instance_from_str=lambda args: json.loads(args[0]),
    is_instance=lambda x: isinstance(x, dict),
    str_from_instance=lambda x: [json.dumps(x)],
)


def test_custom_primitive_registry():
    """Test that we can use a custom primitive registry to parse a custom type."""
    primitive_registry = tyro.constructors.ConstructorRegistry()

    @primitive_registry.primitive_rule
    def json_dict_spec(
        type_info: tyro.constructors.PrimitiveTypeInfo,
    ) -> tyro.constructors.PrimitiveConstructorSpec | None:
        if not (
            type_info.type_origin is dict and get_args(type_info.type) == (str, Any)
        ):
            return None
        return json_constructor_spec

    def main(x: Dict[str, Any]) -> Dict[str, Any]:
        return x

    with primitive_registry:
        assert tyro.cli(main, args=["--x", '{"a": 1}']) == {"a": 1}

    def main_with_default(x: Dict[str, Any] = {"hello": 5}) -> Dict[str, Any]:
        return x

    with primitive_registry:
        assert tyro.cli(main_with_default, args=[]) == {"hello": 5}
        assert tyro.cli(main_with_default, args=["--x", '{"a": 1}']) == {"a": 1}

    def main_with_default_in_list(
        x: List[Dict[str, Any]] = [{"hello": 5}],
    ) -> List[Dict[str, Any]]:
        return x

    with primitive_registry:
        assert tyro.cli(main_with_default_in_list, args=[]) == [{"hello": 5}]
        assert tyro.cli(
            main_with_default_in_list, args=["--x", '{"a": 1}', '{"b": 1}']
        ) == [{"a": 1}, {"b": 1}]


def test_custom_primitive_annotated():
    """Test that we can use typing.Annotated to specify custom constructors."""

    def main(x: Annotated[Dict[str, Any], json_constructor_spec]) -> Dict[str, Any]:
        return x

    assert tyro.cli(main, args=["--x", '{"a": 1}']) == {"a": 1}


def test_custom_primitive_union():
    """Test that we can use typing.Annotated to specify custom constructors."""

    def main(
        x: Union[int, Annotated[Dict[str, Any], json_constructor_spec]],
    ) -> Union[int, Dict[str, Any]]:
        return x

    assert tyro.cli(main, args=["--x", "3"]) == 3
    assert tyro.cli(main, args=["--x", '{"a": 1}']) == {"a": 1}


def _construct_array(
    values: tuple[float, ...], dtype: Literal["float32", "float64"] = "float64"
) -> np.ndarray:
    return np.array(
        values,
        dtype={"float32": np.float32, "float64": np.float64}[dtype],
    )


def test_custom_constructor_numpy() -> None:
    def main(
        array: Annotated[np.ndarray, tyro.conf.arg(constructor=_construct_array)],
    ) -> np.ndarray:
        return array

    assert np.allclose(
        tyro.cli(main, args="--array.values 1 2 3 4 5".split(" ")),
        np.array([1, 2, 3, 4, 5], dtype=np.float64),
    )
    assert (
        tyro.cli(
            main, args="--array.values 1 2 3 4 5 --array.dtype float32".split(" ")
        ).dtype
        == np.float32
    )


def make_list_of_strings_with_minimum_length(args: List[str]) -> List[str]:
    if len(args) == 0:
        raise ValueError("Expected at least one string")
    return args


ListOfStringsWithMinimumLength = Annotated[
    List[str],
    tyro.constructors.PrimitiveConstructorSpec(
        nargs="*",
        metavar="STR [STR ...]",
        is_instance=lambda x: isinstance(x, list)
        and all(isinstance(i, str) for i in x),
        instance_from_str=make_list_of_strings_with_minimum_length,
        str_from_instance=lambda args: args,
    ),
]


def test_min_length_custom_constructor() -> None:
    def main(
        field1: ListOfStringsWithMinimumLength, field2: int = 3
    ) -> ListOfStringsWithMinimumLength:
        del field2
        return field1

    with pytest.raises(SystemExit):
        tyro.cli(main, args=[])
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--field1"])
    assert tyro.cli(main, args=["--field1", "a", "b"]) == ["a", "b"]


def test_min_length_custom_constructor_positional() -> None:
    def main(
        field1: tyro.conf.Positional[ListOfStringsWithMinimumLength], field2: int = 3
    ) -> ListOfStringsWithMinimumLength:
        del field2
        return field1

    with pytest.raises(SystemExit):
        tyro.cli(main, args=[])
    assert tyro.cli(main, args=["a", "b"]) == ["a", "b"]


TupleCustomConstructor = Annotated[
    Tuple[str, ...],
    tyro.constructors.PrimitiveConstructorSpec(
        nargs="*",
        metavar="A TUPLE METAVAR",
        is_instance=lambda x: isinstance(x, tuple)
        and all(isinstance(i, str) for i in x),
        instance_from_str=lambda args: tuple(args),
        str_from_instance=lambda args: list(args),
    ),
]


def test_tuple_custom_constructors() -> None:
    def main(field1: TupleCustomConstructor, field2: int = 3) -> tuple[str, ...]:
        del field2
        return field1

    assert tyro.cli(main, args=["--field1", "a", "b"]) == ("a", "b")
    assert tyro.cli(main, args=["--field1", "a"]) == ("a",)
    assert tyro.cli(main, args=["--field1"]) == ()
    assert "A TUPLE METAVAR" in get_helptext_with_checks(main)


def test_tuple_custom_constructors_positional() -> None:
    def main(
        field1: tyro.conf.Positional[TupleCustomConstructor], field2: int = 3
    ) -> tuple[str, ...]:
        del field2
        return field1

    assert tyro.cli(main, args=["a", "b"]) == ("a", "b")
    assert tyro.cli(main, args=["a"]) == ("a",)
    assert tyro.cli(main, args=[]) == ()
    assert "A TUPLE METAVAR" in get_helptext_with_checks(main)


def test_registry_parameter_primitive() -> None:
    """Test that we can use the registry parameter in tyro.cli() for primitive types."""
    registry = tyro.constructors.ConstructorRegistry()

    @registry.primitive_rule
    def json_dict_spec(
        type_info: tyro.constructors.PrimitiveTypeInfo,
    ) -> tyro.constructors.PrimitiveConstructorSpec | None:
        if not (
            type_info.type_origin is dict and get_args(type_info.type) == (str, Any)
        ):
            return None
        return json_constructor_spec

    def main(x: Dict[str, Any]) -> Dict[str, Any]:
        return x

    # Use registry parameter instead of context manager
    assert tyro.cli(main, args=["--x", '{"a": 1}'], registry=registry) == {"a": 1}


def test_registry_parameter_with_default() -> None:
    """Test that the registry parameter works with default values."""
    registry = tyro.constructors.ConstructorRegistry()

    @registry.primitive_rule
    def json_dict_spec(
        type_info: tyro.constructors.PrimitiveTypeInfo,
    ) -> tyro.constructors.PrimitiveConstructorSpec | None:
        if not (
            type_info.type_origin is dict and get_args(type_info.type) == (str, Any)
        ):
            return None
        return json_constructor_spec

    def main_with_default(x: Dict[str, Any] = {"hello": 5}) -> Dict[str, Any]:
        return x

    # Test with registry parameter
    assert tyro.cli(main_with_default, args=[], registry=registry) == {"hello": 5}
    assert tyro.cli(main_with_default, args=["--x", '{"a": 1}'], registry=registry) == {
        "a": 1
    }


# Define a custom dataclass
@dataclass
class CustomDataWithPrefix:
    value: str


def test_registry_parameter_struct_constructor() -> None:
    """Test that registry parameter works with struct constructors as well."""
    # Create a custom registry
    registry = tyro.constructors.ConstructorRegistry()

    # Define a custom struct constructor that will add a prefix to all string values
    @registry.struct_rule
    def prefix_strings(
        type_info: tyro.constructors.StructTypeInfo,
    ) -> tyro.constructors.StructConstructorSpec | None:
        # Only apply to our CustomDataWithPrefix class
        if type_info.type is not CustomDataWithPrefix:
            return None

        # Create a constructor that adds a prefix to string values
        def prefix_constructor(**kwargs):
            # Add prefix to string value
            if "value" in kwargs and isinstance(kwargs["value"], str):
                kwargs["value"] = "PREFIX_" + kwargs["value"]
            return CustomDataWithPrefix(**kwargs)

        # Create field specs
        field_specs = [
            tyro.constructors.StructFieldSpec(
                name="value",
                type=str,
                default=type_info.default.value
                if type_info.default not in tyro._singleton.DEFAULT_SENTINEL_SINGLETONS
                else tyro._singleton.MISSING_NONPROP,
                helptext=None,
            )
        ]

        # Return a custom struct constructor spec
        return tyro.constructors.StructConstructorSpec(
            instantiate=prefix_constructor, fields=tuple(field_specs)
        )

    def main(data: CustomDataWithPrefix) -> CustomDataWithPrefix:
        return data

    # Test without registry - normal behavior
    result = tyro.cli(main, args=["--data.value", "test"])
    assert result.value == "test"

    # Test with registry - should add prefix
    result = tyro.cli(main, args=["--data.value", "test"], registry=registry)
    assert result.value == "PREFIX_test"


def test_type_primitive_single_class():
    """Test that type[T] works for a single class."""
    def main(optimizer_type: type[int]) -> type[int]:
        return optimizer_type

    assert tyro.cli(main, args=["--optimizer-type", "int"]) is int


def test_type_primitive_union_classes():
    """Test that type[T] | type[U] works for union of types."""
    def main(optimizer_type: type[int] | type[str]) -> type[int] | type[str]:
        return optimizer_type

    assert tyro.cli(main, args=["--optimizer-type", "int"]) is int
    assert tyro.cli(main, args=["--optimizer-type", "str"]) is str


def test_type_primitive_with_subclasses():
    """Test that type[T] includes subclasses in choices."""
    class BaseOptimizer:
        pass

    class SGD(BaseOptimizer):
        pass

    class Adam(BaseOptimizer):
        pass

    def main(optimizer_type: type[BaseOptimizer]) -> type[BaseOptimizer]:
        return optimizer_type

    # Test that we can select the base class
    assert tyro.cli(main, args=["--optimizer-type", "BaseOptimizer"]) is BaseOptimizer
    
    # Test that we can select subclasses
    assert tyro.cli(main, args=["--optimizer-type", "SGD"]) is SGD
    assert tyro.cli(main, args=["--optimizer-type", "Adam"]) is Adam


def test_type_primitive_with_generic_types():
    """Test that type[T] works with generic types like list[int]."""
    from typing import List
    
    def main(container_type: type[List[int]]) -> type[List[int]]:
        return container_type

    assert tyro.cli(main, args=["--container-type", "list[int]"]) is List[int]


def test_type_primitive_helptext():
    """Test that type[T] generates correct help text with choices."""
    def main(optimizer_type: type[int] | type[str]) -> type[int] | type[str]:
        return optimizer_type

    helptext = get_helptext_with_checks(main)
    assert "{int,str}" in helptext


def test_type_primitive_with_default():
    """Test that type[T] works with default values."""
    def main(optimizer_type: type[int] | type[str] = int) -> type[int] | type[str]:
        return optimizer_type

    # Test with default
    assert tyro.cli(main, args=[]) is int
    
    # Test overriding default
    assert tyro.cli(main, args=["--optimizer-type", "str"]) is str


def test_type_primitive_invalid_choice():
    """Test that type[T] raises error for invalid choices."""
    def main(optimizer_type: type[int] | type[str]) -> type[int] | type[str]:
        return optimizer_type

    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--optimizer-type", "invalid"])


def test_type_primitive_torch_classes():
    """Test type[T] with torch.optim classes if torch is available."""
    torch = pytest.importorskip("torch")
    
    def main(
        optimizer_type: type[torch.optim.Adam] | type[torch.optim.SGD]
    ) -> type[torch.optim.Adam] | type[torch.optim.SGD]:
        return optimizer_type

    assert tyro.cli(main, args=["--optimizer-type", "Adam"]) is torch.optim.Adam
    assert tyro.cli(main, args=["--optimizer-type", "SGD"]) is torch.optim.SGD


def test_type_primitive_dataclass_integration():
    """Test type[T] in a dataclass field."""
    from dataclasses import dataclass
    
    @dataclass
    class Config:
        optimizer_type: type[int] | type[str] = int
        learning_rate: float = 0.001

    config = tyro.cli(Config, args=["--optimizer-type", "str", "--learning-rate", "0.1"])
    assert config.optimizer_type is str
    assert config.learning_rate == 0.1
    
    # Test with defaults
    config_default = tyro.cli(Config, args=[])
    assert config_default.optimizer_type is int
    assert config_default.learning_rate == 0.001


def test_type_primitive_str_from_instance():
    """Test that str_from_instance works correctly for type[T]."""
    def main(optimizer_type: type[int] | type[str] = str) -> type[int] | type[str]:
        return optimizer_type

    # The default should be properly converted to string representation
    helptext = get_helptext_with_checks(main)
    assert "default: str" in helptext


def test_type_primitive_complex_inheritance():
    """Test type[T] with more complex inheritance hierarchies."""
    class A:
        pass

    class B(A):
        pass

    class C(B):
        pass

    class D(A):
        pass

    def main(cls_type: type[A]) -> type[A]:
        return cls_type

    # Should be able to select any class in the hierarchy
    assert tyro.cli(main, args=["--cls-type", "A"]) is A
    assert tyro.cli(main, args=["--cls-type", "B"]) is B
    assert tyro.cli(main, args=["--cls-type", "C"]) is C
    assert tyro.cli(main, args=["--cls-type", "D"]) is D
