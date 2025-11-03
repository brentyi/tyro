from __future__ import annotations

import argparse
import contextlib
import io
import os
from typing import Any, Callable

import pytest

import tyro
import tyro._fmtlib
import tyro._strings
from tyro._singleton import MISSING_NONPROP


def get_helptext_with_checks(
    f: Callable[..., Any],
    args: list[str] = ["--help"],
    use_underscores: bool = False,
    default: Any = MISSING_NONPROP,
    config: tuple[Any, ...] = (),
) -> str:
    """Get the helptext for a given tyro with input, while running various
    checks along the way."""
    # Should be empty.
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(
            f,
            args=args,
            use_underscores=use_underscores,
            default=default,
            console_outputs=False,
            config=config,
        )
    assert target.getvalue() == "", target.getvalue()

    # Check tyro.extras.get_parser().
    parser = tyro.extras.get_parser(f, use_underscores=use_underscores)
    assert isinstance(parser, argparse.ArgumentParser)

    # Basic checks for completion scripts.
    with pytest.raises(SystemExit):
        tyro.cli(
            f,
            default=default,
            args=["--tyro-write-completion", "bash", os.devnull],
            config=config,
        )
    for shell in ["bash", "zsh"]:
        for command in ["--tyro-print-completion", "--tyro-write-completion"]:
            target = io.StringIO()
            with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
                if command == "--tyro-write-completion":
                    tyro.cli(
                        f, default=default, args=[command, shell, "-"], config=config
                    )
                else:
                    # `--tyro-print-completion` is deprecated! We should use `--tyro-write-completion` instead.
                    tyro.cli(f, default=default, args=[command, shell], config=config)
            output = target.getvalue()
            # Check that completion was generated (either by shtab or tyro).
            assert "shtab" in output or "tyro" in output

    # Test with underscores
    for shell in ["bash", "zsh"]:
        target = io.StringIO()
        with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
            tyro.cli(
                f,
                default=default,
                args=["--tyro_write_completion", shell, "-"],
                use_underscores=True,
                config=config,
            )
        output = target.getvalue()
        # Check that completion was generated (either by shtab or tyro).
        assert "shtab" in output or "tyro" in output

    # Get the actual helptext.
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(
            f,
            args=args,
            use_underscores=use_underscores,
            default=default,
            config=config,
        )
    return tyro._strings.strip_ansi_sequences(target.getvalue())
