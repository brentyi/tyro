import argparse
import contextlib
import io
import os
from typing import Any, Callable, List

import pytest

import tyro
import tyro._arguments
import tyro._strings


def get_helptext(
    f: Callable,
    args: List[str] = ["--help"],
    use_underscores: bool = False,
    default: Any = None,
) -> str:
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(f, args=args, use_underscores=use_underscores, default=default)

    # Check tyro.extras.get_parser().
    parser = tyro.extras.get_parser(f, use_underscores=use_underscores)
    assert isinstance(parser, argparse.ArgumentParser)

    # Returned parser should have formatting information stripped. External tools rarely
    # support ANSI sequences.
    unformatted_helptext = parser.format_help()
    assert (
        tyro._strings.strip_ansi_sequences(unformatted_helptext) == unformatted_helptext
    )
    unformatted_usage = parser.format_usage()
    assert tyro._strings.strip_ansi_sequences(unformatted_usage) == unformatted_usage

    # Completion scripts; just smoke test for now.
    with pytest.raises(SystemExit), contextlib.redirect_stdout(open(os.devnull, "w")):
        tyro.cli(f, default=default, args=["--tyro-print-completion", "bash"])
    with pytest.raises(SystemExit), contextlib.redirect_stdout(open(os.devnull, "w")):
        tyro.cli(f, default=default, args=["--tyro-print-completion", "zsh"])
    with pytest.raises(SystemExit), contextlib.redirect_stdout(open(os.devnull, "w")):
        tyro.cli(
            f, default=default, args=["--tyro-write-completion", "bash", os.devnull]
        )
    with pytest.raises(SystemExit), contextlib.redirect_stdout(open(os.devnull, "w")):
        tyro.cli(
            f, default=default, args=["--tyro-write-completion", "zsh", os.devnull]
        )

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
