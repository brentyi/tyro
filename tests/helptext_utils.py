import argparse
import contextlib
import io
import os
from typing import Any, Callable, List

import pytest

import tyro
import tyro._arguments
import tyro._strings


def get_helptext_with_checks(
    f: Callable[..., Any],
    args: List[str] = ["--help"],
    use_underscores: bool = False,
    default: Any = None,
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
        )
    assert target.getvalue() == ""

    # Check tyro.extras.get_parser().
    parser = tyro.extras.get_parser(f, use_underscores=use_underscores)
    assert isinstance(parser, argparse.ArgumentParser)

    # Returned parser should have formatting information stripped. External tools rarely
    # support ANSI sequences.
    unformatted_helptext = parser.format_help()
    assert (
        tyro._strings.strip_ansi_sequences(unformatted_helptext) == unformatted_helptext
    ), (
        tyro._strings.strip_ansi_sequences(unformatted_helptext)
        + "\n|\n"
        + unformatted_helptext
    )
    unformatted_usage = parser.format_usage()
    assert tyro._strings.strip_ansi_sequences(unformatted_usage) == unformatted_usage

    # Basic checks for completion scripts.
    with pytest.raises(SystemExit):
        tyro.cli(
            f, default=default, args=["--tyro-write-completion", "bash", os.devnull]
        )
    for shell in ["bash", "zsh"]:
        for command in ["--tyro-print-completion", "--tyro-write-completion"]:
            target = io.StringIO()
            with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
                if command == "--tyro-write-completion":
                    tyro.cli(f, default=default, args=[command, shell, "-"])
                else:
                    # `--tyro-print-completion` is deprecated! We should use `--tyro-write-completion` instead.
                    tyro.cli(f, default=default, args=[command, shell])
            output = target.getvalue()
            assert "shtab" in output

    # Test with underscores
    for shell in ["bash", "zsh"]:
        target = io.StringIO()
        with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
            tyro.cli(
                f,
                default=default,
                args=["--tyro_write_completion", shell, "-"],
                use_underscores=True,
            )
        output = target.getvalue()
        assert "shtab" in output

    # Get the actual helptext.
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(f, args=args, use_underscores=use_underscores, default=default)

    # Check helptext with vs without formatting. This can help catch text wrapping bugs
    # caused by ANSI sequences.
    target2 = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target2):
        tyro._arguments.USE_RICH = False
        tyro.cli(f, default=default, args=args, use_underscores=use_underscores)
        tyro._arguments.USE_RICH = True

    if target2.getvalue() != tyro._strings.strip_ansi_sequences(target.getvalue()):
        raise AssertionError(
            "Potential wrapping bug! These two strings should match:\n"
            + target2.getvalue()
            + "\n\n"
            + tyro._strings.strip_ansi_sequences(target.getvalue())
        )

    return target2.getvalue()
