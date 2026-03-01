"""Test that container instantiation errors are caught and wrapped with helpful messages."""

import dataclasses
from unittest.mock import patch

import pytest

import tyro


def test_container_instantiation_error_handling() -> None:
    """Test that container_type(out) failures are caught and wrapped with helpful error."""

    @dataclasses.dataclass
    class A:
        x: tyro.conf.UseAppendAction[frozenset[str]]

    # Mock frozenset to raise an error during instantiation.
    def failing_frozenset(data):
        raise TypeError("Simulated frozenset failure")

    # Verify that container instantiation errors are caught and wrapped with helpful messages.
    with patch("builtins.frozenset", side_effect=failing_frozenset):
        with pytest.raises(TypeError) as exc_info:
            tyro.cli(A, args="--x a --x b --x c".split(" "))

        # Check that the error message is helpful.
        error_msg = str(exc_info.value)
        assert "Failed to create frozenset from append action" in error_msg
        assert "Simulated frozenset failure" in error_msg


def test_frozenset_works_normally() -> None:
    """Test that frozenset works normally without the mock."""

    @dataclasses.dataclass
    class A:
        x: tyro.conf.UseAppendAction[frozenset[str]]

    result = tyro.cli(A, args="--x a --x b --x c".split(" "))
    assert result.x == frozenset(["a", "b", "c"])
    assert isinstance(result.x, frozenset)
