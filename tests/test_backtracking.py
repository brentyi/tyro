"""Tests for variable-length argument parsing. We compare against a brute-force
reference implementation."""

import itertools
import random
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import pytest
from typing_extensions import Literal

import tyro
from tyro.constructors import (
    ConstructorRegistry,
    PrimitiveConstructorSpec,
    PrimitiveTypeInfo,
)
from tyro.constructors._backtracking import parse_with_backtracking


def get_spec(typ: Any) -> PrimitiveConstructorSpec[Any]:
    spec = ConstructorRegistry.get_primitive_spec(PrimitiveTypeInfo.make(typ, set()))
    assert isinstance(spec, PrimitiveConstructorSpec)
    return spec


def reference_parse(
    args: List[str],
    specs: Tuple[PrimitiveConstructorSpec[Any], ...],
    is_repeating: bool,
    spec_idx: int = 0,
    cycle_has_progress: bool = False,
) -> Optional[List[Any]]:
    """Simple recursive backtracking, without any memoization."""
    if is_repeating:
        if len(args) == 0:
            return [] if spec_idx % len(specs) == 0 else None
        if spec_idx > 0 and spec_idx % len(specs) == 0:
            if not cycle_has_progress:
                return None
            cycle_has_progress = False
    elif spec_idx == len(specs):
        return [] if len(args) == 0 else None

    spec = specs[spec_idx % len(specs)]
    nargs_options: Any
    if spec.nargs == "*":
        nargs_options = range(len(args), -1, -1)
    elif isinstance(spec.nargs, int):
        nargs_options = (spec.nargs,)
    else:
        nargs_options = spec.nargs
    for nargs in nargs_options:
        if nargs > len(args):
            continue
        chunk = args[:nargs]
        if spec.choices is not None and any(arg not in spec.choices for arg in chunk):
            continue
        try:
            value = spec.instance_from_str(chunk)
        except ValueError:
            continue
        rest = reference_parse(
            args[nargs:],
            specs,
            is_repeating,
            spec_idx + 1,
            cycle_has_progress or nargs > 0,
        )
        if rest is not None:
            return [value] + rest
    return None


SPEC_TYPES: List[Tuple[Any, ...]] = [
    (int,),
    (str,),
    (Tuple[int, int],),
    (Tuple[int, str],),
    (Tuple[()],),
    (Literal["a", "1"],),
    (Tuple[Literal["a"], int],),
    (List[int],),
    (Union[int, Tuple[int, int]],),
    (Union[Tuple[int, int, int], Tuple[str, int]],),
    (Union[bool, Tuple[int, int, int], Tuple[str, str]],),
    (str, int),
    (str, Tuple[int, int]),
    (Tuple[str, str], Tuple[int, int]),
    (str, Union[int, Tuple[int, int]]),
    (str, List[int]),
    (List[str], int),
    (List[int], List[str]),
    (int, List[int], Optional[int]),
    (Union[int, Tuple[int, int]], List[int], Tuple[()]),
]


@pytest.mark.parametrize("types", SPEC_TYPES, ids=str)
@pytest.mark.parametrize("is_repeating", [False, True])
def test_matches_reference(types: Tuple[Any, ...], is_repeating: bool) -> None:
    specs = tuple(map(get_spec, types))
    cases = [
        list(args)
        for n in range(5)
        for args in itertools.product(("1", "a", "True"), repeat=n)
    ]
    rng = random.Random(0)
    cases += [
        [rng.choice(("1", "2", "a", "True", "None")) for _ in range(rng.randint(5, 8))]
        for _ in range(50)
    ]
    for args in cases:
        assert parse_with_backtracking(args, specs, is_repeating) == reference_parse(
            args, specs, is_repeating
        ), args


def test_empty_specs() -> None:
    assert parse_with_backtracking([], (), is_repeating=False) == []
    assert parse_with_backtracking(["1"], (), is_repeating=False) is None


def test_ambiguous_failure_is_not_exponential() -> None:
    """This would never finish without memoization."""

    def main(x: List[Union[int, Tuple[int, int], Tuple[int, int, int]]]) -> Any:
        return x

    start = time.perf_counter()
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--x"] + ["1"] * 200 + ["bad"])
    assert time.perf_counter() - start < 10.0


def test_long_sequences() -> None:
    def main(
        a: List[int],
        b: List[Tuple[int, str]],
        c: Dict[str, int],
        d: Dict[str, Tuple[int, float]],
        e: Tuple[Union[int, str], ...],
    ) -> Any:
        return a, b, c, d, e

    n = 3000
    assert tyro.cli(
        main,
        args=["--a"]
        + [str(i) for i in range(n)]
        + ["--b"]
        + [s for i in range(n) for s in (str(i), "x")]
        + ["--c"]
        + [s for i in range(n) for s in (f"k{i}", str(i))]
        + ["--d"]
        + [s for i in range(n) for s in (f"k{i}", str(i), "0.5")]
        + ["--e"]
        + [s for i in range(n) for s in (f"k{i}", str(i))],
    ) == (
        list(range(n)),
        [(i, "x") for i in range(n)],
        {f"k{i}": i for i in range(n)},
        {f"k{i}": (i, 0.5) for i in range(n)},
        tuple(s for i in range(n) for s in (f"k{i}", i)),
    )


def test_replaced_spec() -> None:
    """Optimizations shouldn't be applied if `instance_from_str` is replaced."""
    import dataclasses

    from typing_extensions import Annotated

    spec: Any = dataclasses.replace(
        get_spec(int), instance_from_str=lambda args: int(args[0]) * 2
    )

    def main(
        a: List[Annotated[int, spec]], b: List[Tuple[Annotated[int, spec], int]]
    ) -> Any:
        return a, b

    assert tyro.cli(main, args="--a 1 2 --b 1 2 3 4".split()) == (
        [2, 4],
        [(2, 2), (6, 4)],
    )
