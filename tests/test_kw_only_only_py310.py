import dataclasses

import pytest

import dcargs


@dataclasses.dataclass
class Args:
    a: int
    b: int
    _: dataclasses.KW_ONLY  # type: ignore
    c: int = 7
    d: int  # type: ignore


def test_kw_only():
    assert dcargs.cli(Args, args="--a 5 --b 3 --c 2 --d 1".split(" ")) == Args(
        5, 3, c=2, d=1
    )
    assert dcargs.cli(Args, args="--a 5 --b 3 --d 1".split(" ")) == Args(5, 3, c=7, d=1)
    with pytest.raises(SystemExit):
        dcargs.cli(Args, args="--a 5 --b 3".split(" "))
