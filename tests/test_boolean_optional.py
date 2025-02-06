import dataclasses

import pytest
from helptext_utils import get_helptext_with_checks

import tyro


def test_flag_default_false() -> None:
    """Test for argparse.BooleanOptionalAction-style usage."""

    @dataclasses.dataclass
    class A:
        x: bool

    assert tyro.cli(
        A,
        args=["--x"],
        default=A(False),
    ) == A(True)

    assert tyro.cli(
        A,
        args=["--no-x"],
        default=A(False),
    ) == A(False)

    assert tyro.cli(
        A,
        args=[],
        default=A(False),
    ) == A(False)

    # Type ignore can be removed once TypeForm lands.
    # https://discuss.python.org/t/typeform-spelling-for-a-type-annotation-object-at-runtime/51435
    assert tyro.cli(
        tyro.conf.FlagConversionOff[A],
        args=["--x", "True"],
        default=A(False),  # type: ignore
    ) == A(True)


def test_flag_default_true() -> None:
    """Test for argparse.BooleanOptionalAction-style usage."""

    @dataclasses.dataclass
    class A:
        x: bool

    assert tyro.cli(
        A,
        args=["--x"],
        default=A(True),
    ) == A(True)

    assert tyro.cli(
        A,
        args=["--no-x"],
        default=A(True),
    ) == A(False)

    assert tyro.cli(
        A,
        args=[],
        default=A(True),
    ) == A(True)

    # Type ignore can be removed once TypeForm lands.
    # https://discuss.python.org/t/typeform-spelling-for-a-type-annotation-object-at-runtime/51435
    assert tyro.cli(
        tyro.conf.FlagConversionOff[A],
        args=["--x", "True"],
        default=A(False),  # type: ignore
    ) == A(True)


def test_flag_default_true_helptext() -> None:
    """Test for argparse.BooleanOptionalAction-style usage."""

    @dataclasses.dataclass
    class A:
        x: bool = True

    assert "(default: True)" in get_helptext_with_checks(A)
    assert "(default: False)" not in get_helptext_with_checks(A)
    assert "(default: None)" not in get_helptext_with_checks(A)


def test_flag_no_pairs() -> None:
    """Test for tyro.conf.FlagPairOff."""

    @dataclasses.dataclass
    class A:
        x: tyro.conf.FlagCreatePairsOff[bool]
        y: tyro.conf.FlagCreatePairsOff[bool] = False
        z: tyro.conf.FlagCreatePairsOff[bool] = True

    assert tyro.cli(
        A,
        args=["--x", "True"],
    ) == A(True)
    assert tyro.cli(
        A,
        args=["--x", "True", "--y"],
    ) == A(True, True)
    assert tyro.cli(
        A,
        args=["--x", "True", "--y", "--no-z"],
    ) == A(True, True, False)

    with pytest.raises(SystemExit):
        tyro.cli(
            A,
            args=["--x", "True", "--y", "True"],
        )
    with pytest.raises(SystemExit):
        tyro.cli(
            A,
            args=["--x", "True", "--no-y"],
        )
    with pytest.raises(SystemExit):
        tyro.cli(
            A,
            args=["--x", "True", "--z"],
        )
    with pytest.raises(SystemExit):
        tyro.cli(
            A,
            args=["--x"],
        )
    with pytest.raises(SystemExit):
        tyro.cli(
            A,
            args=["--no-x"],
        )
