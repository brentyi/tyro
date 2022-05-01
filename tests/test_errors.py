import dataclasses
from typing import Generic, Optional, Tuple, TypeVar, Union

import pytest
from typing_extensions import Literal

import dcargs


def test_choices_in_tuples():
    """Due to argparse limitations, all parameters of `choices` must match. In the
    future, we might avoid this by implementing choice restrictions manually."""
    # OK
    @dataclasses.dataclass
    class A:
        x: Tuple[bool, bool]

    assert dcargs.parse(A, args=["--x", "True", "False"]) == A((True, False))

    # OK
    @dataclasses.dataclass
    class A:
        x: Tuple[bool, Literal["True", "False"]]

    assert dcargs.parse(A, args=["--x", "True", "False"]) == A((True, "False"))

    # Not OK: same argument, different choices.
    @dataclasses.dataclass
    class A:
        x: Tuple[bool, Literal["True", "False", "None"]]

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.parse(A, args=["--x", "True", "False"])


def test_nested_sequence_types():
    """Unclear how to handle nested sequences, so we don't support them."""

    @dataclasses.dataclass
    class A:
        x: Tuple[Tuple[int, ...], ...]

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.parse(A, args=["--x", "0", "1"])


def test_nested_optional_types():
    """Unclear how to handle optionals nested in other types, so we don't support
    them.

    In the future, we might support "None" as a special-case keyword. But this is a bit
    weird because Optional[str] might interprete "None" as either a string or an actual
    `None` value."""

    @dataclasses.dataclass
    class A:
        x: Tuple[Optional[int], ...]

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.parse(A, args=["--x", "0", "1"])


def test_multiple_subparsers():
    """argparse doesn't support multiple subparsers."""

    @dataclasses.dataclass
    class Subcommmand1:
        pass

    @dataclasses.dataclass
    class Subcommand2:
        pass

    @dataclasses.dataclass
    class MultipleSubparsers:
        x: Union[Subcommmand1, Subcommand2]
        y: Union[Subcommmand1, Subcommand2]

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.parse(MultipleSubparsers)


# Must be global.
@dataclasses.dataclass
class _CycleDataclass:
    x: "_CycleDataclass"


def test_cycle():
    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.parse(_CycleDataclass)


def test_generic_inherited():
    """Inheriting from generics is currently not implemented. It's unclear whether this
    is feasible, because generics are lost in the mro:
    https://github.com/python/typing/issues/777"""

    class UnrelatedParentClass:
        pass

    T = TypeVar("T")

    @dataclasses.dataclass
    class ActualParentClass(Generic[T]):
        x: T  # Documentation 1

        # Documentation 2
        y: T

        z: T = 3
        """Documentation 3"""

    @dataclasses.dataclass
    class ChildClass(UnrelatedParentClass, ActualParentClass[int]):
        pass

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.parse(ChildClass, args=["--x", 1, "--y", 2, "--z", 3])
