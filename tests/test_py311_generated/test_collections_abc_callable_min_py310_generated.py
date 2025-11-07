# mypy: ignore-errors

import dataclasses
from collections.abc import Callable
from typing import ClassVar

import pytest

import tyro
from tyro.constructors import UnsupportedTypeAnnotationError


def test_collections_abc_callable_fixed() -> None:
    """Test that collections.abc.Callable with default value is treated as fixed."""

    def main(x: Callable[[int], int] = lambda x: x * 2) -> Callable[[int], int]:
        return x

    assert tyro.cli(main, args=[])(3) == 6
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--x", "something"])


def test_collections_abc_callable_fixed_dataclass_type() -> None:
    """Test untyped collections.abc.Callable with default value."""

    def dummy():
        return 5

    def main(x: Callable = dummy) -> Callable:
        return x

    assert tyro.cli(main, args=[]) is dummy
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--x", "something"])


def test_collections_abc_callable_ellipsis() -> None:
    """Test collections.abc.Callable with ellipsis in dataclass."""

    @dataclasses.dataclass
    class SimpleCallable:
        x: Callable[..., None] = lambda: None

    assert tyro.cli(SimpleCallable, args=[]) == SimpleCallable()


def test_collections_abc_callable_classvar() -> None:
    """Test ClassVar[collections.abc.Callable[...]] within dataclass (issue #314)."""

    @dataclasses.dataclass
    class Cmd:
        x: int
        FUNC: ClassVar[Callable[[int], str]] = str

    # This should work without errors
    result = tyro.cli(Cmd, args=["--x", "42"])
    assert result.x == 42
    assert result.FUNC is str


def test_collections_abc_callable_classvar_complex() -> None:
    """Test more complex ClassVar[collections.abc.Callable] scenarios."""

    @dataclasses.dataclass
    class ComplexCmd:
        x: int = 1
        y: float = 2.0

        # Various ClassVar Callable patterns that should not interfere with CLI
        FUNC1: ClassVar[Callable[[int], str]] = str
        FUNC2: ClassVar[Callable[..., None]] = lambda: None
        FUNC3: ClassVar[Callable] = print

    result = tyro.cli(ComplexCmd, args=["--x", "10", "--y", "3.14"])
    assert result.x == 10
    assert result.y == 3.14
    assert result.FUNC1 is str
    assert result.FUNC3 is print


def test_collections_abc_callable_classvar_zero_params() -> None:
    """Test ClassVar[collections.abc.Callable[[], ReturnType]] with zero parameters."""

    @dataclasses.dataclass
    class ZeroParamCmd:
        x: int
        FUNC: ClassVar[Callable[[], str]] = lambda: "hello"

    result = tyro.cli(ZeroParamCmd, args=["--x", "5"])
    assert result.x == 5


def test_collections_abc_callable_instance_var() -> None:
    """Test instance variable with collections.abc.Callable type should fail with proper error."""

    @dataclasses.dataclass
    class BadCmd:
        x: int
        # This should fail with UnsupportedTypeAnnotationError, not the cryptic TypeError
        y: Callable[[int], str]

    with pytest.raises(UnsupportedTypeAnnotationError):
        tyro.cli(BadCmd, args=["--x", "42"])


def test_collections_abc_callable_with_generic_resolution() -> None:
    """Test collections.abc.Callable with type parameter resolution in generic context.

    This test exercises the callable_was_flattened code path in TypeParamResolver
    by using collections.abc.Callable (which lacks copy_with()) in a generic context
    where type parameters need to be resolved.
    """
    from typing import Generic, TypeVar

    T = TypeVar("T")

    @dataclasses.dataclass
    class GenericContainer(Generic[T]):
        x: int
        # ClassVar with Callable that has a type parameter.
        FUNC: ClassVar[Callable[[T], str]] = str  # pyright: ignore[reportGeneralTypeIssues]

    # When we use GenericContainer[int], the T in Callable[[T], str] should resolve to int.
    result = tyro.cli(GenericContainer[int], args=["--x", "42"])
    assert result.x == 42
    # The ClassVar should still be accessible and the type should be resolved correctly.
    assert result.FUNC is str


def test_collections_abc_callable_type_param_resolution_direct() -> None:
    """Test that collections.abc.Callable type parameters are correctly resolved.

    This is a more direct unit test that verifies the callable_was_flattened code path
    in TypeParamResolver (lines 481-485 and 522-530 in _resolver.py).
    """
    from typing import TypeVar, get_args

    from tyro._resolver import TypeParamResolver

    T = TypeVar("T")

    # Create a Callable type with a TypeVar parameter.
    # collections.abc.Callable stores args as ([param_types...], return_type).
    callable_type = Callable[[T, int], str]  # pyright: ignore[reportGeneralTypeIssues]

    # Push a type parameter assignment to resolve T -> float.
    TypeParamResolver.param_assignments.append({T: float})

    try:
        # This should trigger the callable_was_flattened path because:
        # 1. origin is collections.abc.Callable (not typing.Callable).
        # 2. First arg is a list: [T, int].
        # 3. collections.abc.Callable lacks copy_with(), so we need special handling.
        resolved = TypeParamResolver.resolve_params_and_aliases(callable_type)  # pyright: ignore[reportArgumentType]

        # Verify the result: T should be replaced with float.
        resolved_args = get_args(resolved)
        assert len(resolved_args) == 2
        assert resolved_args[0] == [float, int]  # Parameter types.
        assert resolved_args[1] is str  # Return type.
    finally:
        TypeParamResolver.param_assignments.pop()
