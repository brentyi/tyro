import dataclasses

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
