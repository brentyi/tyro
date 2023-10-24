from dataclasses import field, make_dataclass

import pytest

import tyro


def test_dynamic():
    B = make_dataclass("B", [("c", int, field())])
    A = make_dataclass("A", [("b", B, field())])

    with pytest.raises(SystemExit):
        tyro.cli(A, args=[])
    assert tyro.cli(A, args=["--b.c", "5"]) == A(b=B(c=5))
