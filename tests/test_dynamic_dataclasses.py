from dataclasses import field, make_dataclass

import pytest

import dcargs


def test_dynamic():
    B = make_dataclass("B", [("c", int, field())])
    A = make_dataclass("A", [("b", B, field())])

    with pytest.raises(SystemExit):
        dcargs.cli(A, args=[])
    assert dcargs.cli(A, args=["--b.c", "5"]) == A(b=B(c=5))
