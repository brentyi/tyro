"""End-to-end regression tests for fish completion generation.

These tests target specific bugs/edge cases found during review of the fish
completion feature. They drive a *real* ``fish`` binary (when available) by
sourcing the generated completion script and invoking ``complete
--do-complete``, then asserting on the candidates fish returns.

Each test is written to PASS once the corresponding bug is fixed, so a failure
here pinpoints a current defect rather than describing intended-but-absent
behavior.

Findings covered (see review):
- B1: quote/backslash/dollar in a default or description must not corrupt the
      generated script (it currently does -> python SyntaxError when sourced).
- B2: a bare prog name must not yield duplicate completion candidates.
- B3: the argparse (shtab) backend must raise a clean tyro-level error for
      fish, not a raw shtab NotImplementedError.
- B5: covered by test_completion_fish.py's pytestmark (separate fix).
"""

import contextlib
import dataclasses
import io
import shutil
import subprocess
import sys
from typing import List

import pytest

import tyro

pytestmark = [
    pytest.mark.skipif(
        sys.platform == "win32", reason="Fish not available on Windows"
    ),
    pytest.mark.skipif(
        shutil.which("fish") is None, reason="Fish shell not installed"
    ),
]


def _generate_fish_script(cls, prog: str = "prog") -> str:
    """Generate a fish completion script for ``cls`` via the tyro backend."""
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(cls, args=["--tyro-print-completion", "fish"], prog=prog)
    return target.getvalue()


def _raw_complete(completion_script: str, command_line: str) -> List[str]:
    """Source ``completion_script`` in fish and return raw candidate lines.

    Unlike the helper in ``test_completion_fish.py``, this returns the full
    ``candidate\tdescription`` lines (not just the left side) so callers can
    assert on duplicates and descriptions.
    """
    test_script = f"""
    {completion_script}
    complete --do-complete='{command_line}'
    """
    proc = subprocess.run(
        ["fish", "-c", test_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"fish completion failed (rc={proc.returncode}):\n"
            f"{proc.stderr.decode(errors='replace')}"
        )
    out = proc.stdout.decode().strip()
    return out.split("\n") if out else []


def _candidates(completion_script: str, command_line: str) -> List[str]:
    """Return just the candidate words (left of the tab)."""
    return [line.split("\t")[0] for line in _raw_complete(completion_script, command_line)]


# ---------------------------------------------------------------------------
# B1: special characters in defaults / descriptions must not corrupt the script.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "default",
    [
        "don't",  # single quote
        'say "hi"',  # double quote
        "back\\slash",  # backslash
        "cost $5",  # dollar sign
        'mix \'a\' "b" \\ $c',  # all of the above
    ],
)
def test_special_chars_in_default_do_not_break_script(backend: str, default: str) -> None:
    """A default value with shell-special chars must still produce a usable script.

    Regression for B1: the spec is embedded via ``repr(spec)`` inside a fish
    double-quoted string with only ``"`` escaped, so ``"``, ``\\`` and ``$`` in a
    default (or description) corrupt the embedded python and fish raises an error
    when the script is sourced.
    """
    if backend != "tyro":
        pytest.skip("Testing tyro-specific completion behavior")

    @dataclasses.dataclass
    class Config:
        value: str = default

    script = _generate_fish_script(Config)

    # Sourcing + completing must not raise (the bug surfaces as a python
    # SyntaxError propagated through fish -> non-zero return code).
    candidates = _candidates(script, "prog --")
    assert "--value" in candidates


def test_description_with_quotes_does_not_break_script(backend: str) -> None:
    """A help string containing quotes must not corrupt the generated script.

    Regression for B1: descriptions flow into the same embedded spec as defaults.
    """
    if backend != "tyro":
        pytest.skip("Testing tyro-specific completion behavior")

    from typing_extensions import Annotated

    @dataclasses.dataclass
    class Config:
        value: Annotated[int, tyro.conf.arg(help='use "double" and \'single\' $quotes')] = 1

    script = _generate_fish_script(Config)
    candidates = _candidates(script, "prog --")
    assert "--value" in candidates


# ---------------------------------------------------------------------------
# B2: a bare prog name must not produce duplicate candidates.
# ---------------------------------------------------------------------------


def test_no_duplicate_completions_for_bare_prog(backend: str) -> None:
    """Completions must be unique when prog has no path component.

    Regression for B2: the script registers ``complete --command {prog}`` and
    then unconditionally ``complete --command (basename {prog})``. For a bare
    prog these are identical, so every candidate appears twice.
    """
    if backend != "tyro":
        pytest.skip("Testing tyro-specific completion behavior")

    @dataclasses.dataclass
    class Config:
        alpha: int = 1
        beta: int = 2
        gamma: int = 3

    script = _generate_fish_script(Config, prog="myprog")
    candidates = _candidates(script, "myprog --")

    assert len(candidates) == len(set(candidates)), (
        f"Duplicate completion candidates returned: {candidates}"
    )


def test_no_duplicate_completions_for_dotslash_prog(backend: str) -> None:
    """No duplicates when prog is invoked as ``./name`` either.

    Regression for B2: the ``./$_prog_basename`` registration must also be
    guarded; when prog == './myprog', basename is 'myprog' and './myprog'
    collides with the primary registration.
    """
    if backend != "tyro":
        pytest.skip("Testing tyro-specific completion behavior")

    @dataclasses.dataclass
    class Config:
        alpha: int = 1
        beta: int = 2

    script = _generate_fish_script(Config, prog="./myprog")
    candidates = _candidates(script, "./myprog --")

    assert len(candidates) == len(set(candidates)), (
        f"Duplicate completion candidates returned: {candidates}"
    )


# ---------------------------------------------------------------------------
# B3: argparse/shtab backend must reject fish with a clean error.
# ---------------------------------------------------------------------------


def test_argparse_backend_fish_clean_error(backend: str) -> None:
    """argparse backend + fish should raise a clear tyro-level error.

    Regression for B3: shtab does not support fish, so the argparse path raises
    a raw ``NotImplementedError`` from shtab. tyro should instead raise an error
    whose message mentions fish and points at the tyro backend.
    """
    if backend != "argparse":
        pytest.skip("Testing argparse/shtab backend behavior")

    @dataclasses.dataclass
    class Config:
        value: int = 1

    with pytest.raises(Exception) as exc_info:
        tyro.cli(Config, args=["--tyro-print-completion", "fish"], prog="prog")

    message = str(exc_info.value).lower()
    # Must mention fish...
    assert "fish" in message, (
        f"Expected a clear fish-related error message, got: {exc_info.value!r}"
    )
    # ...and point the user at the tyro backend, rather than leaking shtab's raw
    # "shell (fish) must be in bash,zsh,tcsh" NotImplementedError.
    assert "tyro" in message and "shtab" not in message, (
        f"Expected a tyro-level error pointing at the tyro backend, got: "
        f"{type(exc_info.value).__name__}: {exc_info.value!r}"
    )
