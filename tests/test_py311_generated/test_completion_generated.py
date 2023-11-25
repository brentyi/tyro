import contextlib
import dataclasses
import io

import pytest

import tyro


# https://github.com/brentyi/tyro/issues/9
@dataclasses.dataclass(frozen=True)
class Subtype:
    data: int = 1


@dataclasses.dataclass(frozen=True)
class TypeA:
    subtype: Subtype = Subtype(1)


@dataclasses.dataclass(frozen=True)
class TypeB:
    subtype: Subtype = Subtype(2)


@dataclasses.dataclass(frozen=True)
class Wrapper:
    supertype: (TypeA | TypeB) = TypeA()


def test_bash():
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(Wrapper, args=["--tyro-print-completion", "bash"])
    assert "# AUTOMATICALLY GENERATED by `shtab`" in target.getvalue()


def test_zsh():
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(Wrapper, args=["--tyro-print-completion", "zsh"])
    assert "# AUTOMATICALLY GENERATED by `shtab`" in target.getvalue()
