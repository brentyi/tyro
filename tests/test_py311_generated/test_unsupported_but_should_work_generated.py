"""Tests for features that are not officially features, but should work.

Includes things like omegaconf.MISSING, attrs, etc, which mostly work but either likely
have corner cases or just seem sketchy.
"""

from typing import Tuple

import omegaconf
import pytest

import tyro


def test_omegaconf_missing():
    """Passing in a omegaconf.MISSING default; this will mark an argument as required."""

    def main(
        required_a: int,
        optional: int = 3,
        required_b: int = None,  # type: ignore
    ) -> Tuple[int, int, int]:
        return (required_a, optional, required_b)  # type: ignore

    assert tyro.cli(
        main, args="--required-a 3 --optional 4 --required-b 5".split(" ")
    ) == (3, 4, 5)
    assert tyro.cli(main, args="--required-a 3 --required-b 5".split(" ")) == (
        3,
        3,
        5,
    )

    with pytest.raises(SystemExit):
        tyro.cli(main, args="--required-a 3 --optional 4")
    with pytest.raises(SystemExit):
        tyro.cli(main, args="--required-a 3")

    def main2(
        required_a: int,
        optional: int = 3,
        required_b: int = omegaconf.MISSING,
    ) -> Tuple[int, int, int]:
        return (required_a, optional, required_b)

    assert tyro.cli(
        main2, args="--required-a 3 --optional 4 --required-b 5".split(" ")
    ) == (3, 4, 5)
    assert tyro.cli(main2, args="--required-a 3 --required-b 5".split(" ")) == (
        3,
        3,
        5,
    )

    with pytest.raises(SystemExit):
        tyro.cli(main2, args="--required-a 3 --optional 4")
    with pytest.raises(SystemExit):
        tyro.cli(main2, args="--required-a 3")
