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


def test_disallow_none_bool_flag() -> None:
    """Test for DisallowNone[bool | None] flag syntax (issue #381)."""

    @dataclasses.dataclass
    class A:
        x: tyro.conf.DisallowNone[bool | None] = None

    # Test that flag syntax works.
    assert tyro.cli(A, args=["--x"]) == A(True)
    assert tyro.cli(A, args=["--no-x"]) == A(False)
    assert tyro.cli(A, args=[]) == A(None)

    # Test with different default values.
    @dataclasses.dataclass
    class B:
        x: tyro.conf.DisallowNone[bool | None] = False

    assert tyro.cli(B, args=["--x"]) == B(True)
    assert tyro.cli(B, args=["--no-x"]) == B(False)
    assert tyro.cli(B, args=[]) == B(False)

    @dataclasses.dataclass
    class C:
        x: tyro.conf.DisallowNone[bool | None] = True

    assert tyro.cli(C, args=["--x"]) == C(True)
    assert tyro.cli(C, args=["--no-x"]) == C(False)
    assert tyro.cli(C, args=[]) == C(True)


def test_disallow_none_bool_helptext() -> None:
    """Test that DisallowNone[bool | None] shows flag-style helptext."""

    @dataclasses.dataclass
    class A:
        x: tyro.conf.DisallowNone[bool | None] = None

    helptext = get_helptext_with_checks(A)
    # Should show --x | --no-x instead of {True,False}.
    assert "--x" in helptext or "--x," in helptext
    assert "--no-x" in helptext
    assert "{True,False}" not in helptext
    assert "(default: None)" in helptext
