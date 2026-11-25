"""Constructor specifications are part of our public API, and should behave like standard
frozen dataclasses."""

import copy
import dataclasses
import pickle
from typing import Any, List

import pytest

import tyro
from tyro.constructors import (
    PrimitiveConstructorSpec,
    PrimitiveTypeInfo,
    StructConstructorSpec,
    StructFieldSpec,
    StructTypeInfo,
)


def _from_str(args: List[str]) -> int:
    return int(args[0])


def _is_instance(x: Any) -> bool:
    return isinstance(x, int)


def _to_str(x: Any) -> List[str]:
    return [str(x)]


def make_spec() -> PrimitiveConstructorSpec[int]:
    return PrimitiveConstructorSpec(
        nargs=1,
        metavar="X",
        instance_from_str=_from_str,
        is_instance=_is_instance,
        str_from_instance=_to_str,
    )


@pytest.mark.parametrize(
    "cls",
    [
        PrimitiveConstructorSpec,
        PrimitiveTypeInfo,
        StructConstructorSpec,
        StructFieldSpec,
        StructTypeInfo,
    ],
)
def test_is_dataclass(cls: Any) -> None:
    assert dataclasses.is_dataclass(cls)
    assert len(dataclasses.fields(cls)) > 0


def test_equality_and_hash() -> None:
    assert make_spec() == make_spec()
    assert hash(make_spec()) == hash(make_spec())
    assert make_spec() != dataclasses.replace(make_spec(), metavar="Y")
    assert make_spec() != 3


def test_replace() -> None:
    spec = dataclasses.replace(make_spec(), metavar="Y", choices=("1", "2"))
    assert spec.metavar == "Y"
    assert spec.choices == ("1", "2")
    assert spec.instance_from_str is _from_str


def test_repr() -> None:
    field = StructFieldSpec(name="x", type=int, default=3)
    assert repr(field) == (
        "StructFieldSpec(name='x', type=<class 'int'>, default=3, helptext=None, "
        "_call_argname=None, is_default_overridden=None)"
    )


def test_asdict() -> None:
    assert dataclasses.asdict(make_spec())["metavar"] == "X"


def test_frozen() -> None:
    spec = make_spec()
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.metavar = "Y"  # type: ignore
    with pytest.raises(dataclasses.FrozenInstanceError):
        del spec.metavar


def test_copy_and_pickle() -> None:
    spec = make_spec()
    assert copy.copy(spec) == spec
    assert copy.deepcopy(spec) == spec
    assert pickle.loads(pickle.dumps(spec)) == spec


def test_subclass() -> None:
    @dataclasses.dataclass(frozen=True)
    class CustomField(StructFieldSpec):
        extra: int = 5

    field = CustomField(name="x", type=int, default=3, extra=10)
    assert (field.name, field.type, field.default, field.extra) == ("x", int, 3, 10)
    assert dataclasses.replace(field, name="y").name == "y"


def test_parse_error_events() -> None:
    from tyro import _errors

    event = _errors.BadValue(
        prog="p",
        argument=None,  # type: ignore
        reason="fixed",
        offending_value="3",
    )
    assert isinstance(event, _errors.ParseErrorEvent)
    assert dataclasses.replace(event, prog="q").prog == "q"
    assert event == dataclasses.replace(event)
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.prog = "q"  # type: ignore
    with pytest.raises(TypeError):
        _errors.BadValue(prog="p")  # type: ignore


def test_concurrent_calls() -> None:
    """Simple calls to tyro.cli() should be able to run concurrently."""
    from concurrent.futures import ThreadPoolExecutor

    def call(i: int) -> Any:
        @dataclasses.dataclass
        class Config:
            x: "List[int]"
            y: int = 3

        out = tyro.cli(Config, args=["--x", str(i), "--y", str(i)])
        return out.x, out.y

    with ThreadPoolExecutor(8) as executor:
        outputs = list(executor.map(call, range(200)))
    assert outputs == [([i], i) for i in range(200)]
