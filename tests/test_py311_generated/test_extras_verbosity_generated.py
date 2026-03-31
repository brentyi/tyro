# mypy: ignore-errors
import dataclasses
import logging
from pathlib import Path
from typing import Annotated

import pytest

import tyro
from tyro.extras import Verbosity


@pytest.mark.parametrize(
    "verbose,quiet,expected",
    [
        (0, 0, logging.WARNING),
        (1, 0, logging.INFO),
        (2, 0, logging.DEBUG),
        (0, 1, logging.ERROR),
        (0, 2, logging.CRITICAL),
        (99, 0, logging.DEBUG),
        (0, 99, logging.CRITICAL),
    ],
)
def test_log_level(verbose: int, quiet: int, expected: int) -> None:
    assert Verbosity(verbose=verbose, quiet=quiet).log_level() == expected


@pytest.mark.parametrize(
    "verbose,quiet,default,expected",
    [
        (0, 0, logging.INFO, logging.INFO),
        (1, 0, logging.INFO, logging.DEBUG),
    ],
)
def test_log_level_custom_default(
    verbose: int, quiet: int, default: int, expected: int
) -> None:
    assert (
        Verbosity(verbose=verbose, quiet=quiet).log_level(default=default) == expected
    )


def test_verbosity_default_is_warning() -> None:
    assert Verbosity().log_level() == logging.WARNING


def test_verbosity_is_frozen() -> None:
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        Verbosity(verbose=0, quiet=0).verbose = 1  # type: ignore[misc]


def test_cli_defaults() -> None:
    assert tyro.cli(Verbosity, args=[]) == Verbosity(verbose=0, quiet=0)


def test_cli_short_verbose_alias() -> None:
    assert tyro.cli(Verbosity, args=["-v"]) == Verbosity(verbose=1, quiet=0)
    assert tyro.cli(Verbosity, args=["-vv"]) == Verbosity(verbose=2, quiet=0)
    assert tyro.cli(Verbosity, args=["-vvv"]) == Verbosity(verbose=3, quiet=0)


def test_cli_short_quiet_alias() -> None:
    assert tyro.cli(Verbosity, args=["-q"]) == Verbosity(verbose=0, quiet=1)
    assert tyro.cli(Verbosity, args=["-qq"]) == Verbosity(verbose=0, quiet=2)


def test_cli_long_verbose_flag() -> None:
    assert tyro.cli(Verbosity, args=["--verbose"]) == Verbosity(verbose=1, quiet=0)
    assert tyro.cli(Verbosity, args=["--verbose", "--verbose"]) == Verbosity(
        verbose=2, quiet=0
    )


def test_cli_long_quiet_flag() -> None:
    assert tyro.cli(Verbosity, args=["--quiet"]) == Verbosity(verbose=0, quiet=1)


def test_cli_mutually_exclusive() -> None:
    """--verbose and --quiet must not be combined."""
    with pytest.raises(SystemExit):
        tyro.cli(Verbosity, args=["-v", "-q"])


def test_nested_defaults() -> None:
    @dataclasses.dataclass
    class App:
        path: Path = dataclasses.field(default_factory=Path.cwd)
        verbosity: Verbosity = dataclasses.field(default_factory=Verbosity)

    assert tyro.cli(App, args=[]) == App()


def test_nested_short_alias() -> None:
    @dataclasses.dataclass
    class App:
        verbosity: Verbosity = dataclasses.field(default_factory=Verbosity)

    assert tyro.cli(App, args=["-vv"]).verbosity == Verbosity(verbose=2, quiet=0)


def test_nested_prefixed_long_flag() -> None:
    """Without OmitArgPrefixes, long flags carry the field-name prefix."""

    @dataclasses.dataclass
    class App:
        verbosity: Verbosity = dataclasses.field(default_factory=Verbosity)

    result = tyro.cli(App, args=["--verbosity.verbose", "--verbosity.verbose"])
    assert result.verbosity == Verbosity(verbose=2, quiet=0)


def test_omit_prefixes_long_verbose() -> None:
    @dataclasses.dataclass
    class App:
        verbosity: Annotated[Verbosity, tyro.conf.OmitArgPrefixes] = dataclasses.field(
            default_factory=Verbosity
        )

    result = tyro.cli(App, args=["--verbose", "--verbose"])
    assert result.verbosity == Verbosity(verbose=2, quiet=0)


def test_omit_prefixes_long_quiet() -> None:
    @dataclasses.dataclass
    class App:
        verbosity: Annotated[Verbosity, tyro.conf.OmitArgPrefixes] = dataclasses.field(
            default_factory=Verbosity
        )

    assert tyro.cli(App, args=["--quiet"]).verbosity == Verbosity(verbose=0, quiet=1)


def test_omit_prefixes_short_aliases_still_work() -> None:
    @dataclasses.dataclass
    class App:
        verbosity: Annotated[Verbosity, tyro.conf.OmitArgPrefixes] = dataclasses.field(
            default_factory=Verbosity
        )

    assert tyro.cli(App, args=["-vvv"]).verbosity == Verbosity(verbose=3, quiet=0)


def test_omit_prefixes_mutually_exclusive() -> None:
    @dataclasses.dataclass
    class App:
        verbosity: Annotated[Verbosity, tyro.conf.OmitArgPrefixes] = dataclasses.field(
            default_factory=Verbosity
        )

    with pytest.raises(SystemExit):
        tyro.cli(App, args=["--verbose", "--quiet"])


def test_omit_prefixes_log_level_roundtrip() -> None:
    @dataclasses.dataclass
    class App:
        verbosity: Annotated[Verbosity, tyro.conf.OmitArgPrefixes] = dataclasses.field(
            default_factory=Verbosity
        )

    assert tyro.cli(App, args=["-vv"]).verbosity.log_level() == logging.DEBUG
