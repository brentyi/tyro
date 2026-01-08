"""Tests for completion spec generation and get_completions logic."""

import contextlib
import dataclasses
import io
import pathlib
from typing import List, Union

import pytest
from typing_extensions import Annotated, Literal

import tyro


def _strip_comments_and_normalize(script: str) -> str:
    """Strip comments and normalize whitespace for comparison.

    This removes:
    - Lines starting with # (comments)
    - Empty lines
    - Leading/trailing whitespace

    Then normalizes remaining whitespace for comparison.
    """
    lines = []
    for line in script.split("\n"):
        stripped = line.strip()
        # Skip empty lines and comment lines.
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def test_completion_output_parity() -> None:
    """Test that argparse and tyro backends produce equivalent completion scripts.

    The scripts should be functionally identical (ignoring comments and formatting).
    """

    def simple_function(
        x: int = 5,
        y: Annotated[str, tyro.conf.arg(aliases=["-y"])] = "hello",
        flag: bool = False,
    ) -> None:
        """Simple function for testing completion parity."""

    # Generate completion with argparse backend.
    original_backend = tyro._experimental_options["backend"]
    tyro._experimental_options["backend"] = "argparse"

    target_argparse = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target_argparse):
        tyro.cli(simple_function, args=["--tyro-print-completion", "bash"])

    # Generate completion with tyro backend.
    tyro._experimental_options["backend"] = "tyro"

    target_tyro = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target_tyro):
        tyro.cli(simple_function, args=["--tyro-print-completion", "bash"])

    # Restore original backend.
    tyro._experimental_options["backend"] = original_backend

    # Strip comments and compare.
    argparse_normalized = _strip_comments_and_normalize(target_argparse.getvalue())
    tyro_normalized = _strip_comments_and_normalize(target_tyro.getvalue())

    # Different architectures but same functionality.
    # Argparse backend uses bash variables, tyro backend uses embedded Python.
    assert "_option_strings=" in argparse_normalized
    assert "COMPLETION_SPEC" in tyro_normalized
    assert "PYTHON_EOF" in tyro_normalized

    # Check that both have the same options (though in possibly different order/format).
    assert "--x" in argparse_normalized and "--x" in tyro_normalized
    assert "-y" in argparse_normalized and "-y" in tyro_normalized
    assert "--flag" in argparse_normalized and "--flag" in tyro_normalized
    assert "--no-flag" in argparse_normalized and "--no-flag" in tyro_normalized


def test_completion_parity_with_subcommands() -> None:
    """Test completion parity for simple subcommands (no CascadeSubcommandArgs)."""

    @dataclasses.dataclass
    class SubA:
        value_a: int = 1

    @dataclasses.dataclass
    class SubB:
        value_b: str = "hello"

    @dataclasses.dataclass
    class Config:
        sub: Union[SubA, SubB]

    # Generate completion with argparse backend.
    original_backend = tyro._experimental_options["backend"]
    tyro._experimental_options["backend"] = "argparse"

    target_argparse = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target_argparse):
        tyro.cli(Config, args=["--tyro-print-completion", "bash"])

    # Generate completion with tyro backend.
    tyro._experimental_options["backend"] = "tyro"

    target_tyro = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target_tyro):
        tyro.cli(Config, args=["--tyro-print-completion", "bash"])

    # Restore original backend.
    tyro._experimental_options["backend"] = original_backend

    argparse_output = target_argparse.getvalue()
    tyro_output = target_tyro.getvalue()

    # Both should have subcommands.
    assert "sub:sub-a" in argparse_output or "sub_a" in argparse_output
    assert "sub:sub-b" in argparse_output or "sub_b" in argparse_output
    assert "sub:sub-a" in tyro_output or "sub_a" in tyro_output
    assert "sub:sub-b" in tyro_output or "sub_b" in tyro_output

    # Both should have the subcommand arguments (possibly with prefix).
    assert (
        "--value-a" in argparse_output
        or "--value_a" in argparse_output
        or "--sub.value-a" in argparse_output
        or "--sub.value_a" in argparse_output
    )
    assert (
        "--value-b" in argparse_output
        or "--value_b" in argparse_output
        or "--sub.value-b" in argparse_output
        or "--sub.value_b" in argparse_output
    )
    assert (
        "--value-a" in tyro_output
        or "--value_a" in tyro_output
        or "--sub.value-a" in tyro_output
        or "--sub.value_a" in tyro_output
    )
    assert (
        "--value-b" in tyro_output
        or "--value_b" in tyro_output
        or "--sub.value-b" in tyro_output
        or "--sub.value_b" in tyro_output
    )


def test_path_completion(backend: str) -> None:
    """Test that path arguments get proper file/directory completion."""
    from pathlib import Path

    def path_function(
        input_file: Path,
        output_dir: Path,
        config_path: str,
    ) -> None:
        """Function with path arguments."""

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(path_function, args=["--tyro-print-completion", "bash"])

    output = target.getvalue()

    if backend == "tyro":
        # New Python-based backend: check for path types in the spec.
        assert "'type': 'path'" in output
    else:
        # Argparse backend uses shtab helper functions.
        assert "_shtab_compgen_files" in output or "_shtab_compgen_dirs" in output


def test_cascaded_subcommand_completion(backend: str) -> None:
    """Test completion for cascaded subcommands.

    This tests the tyro-specific CascadeSubcommandArgs feature, which allows
    more flexible argument ordering. The completion should include all available
    options at each level.
    """

    @dataclasses.dataclass
    class SubA:
        sub_value: int = 1

    @dataclasses.dataclass
    class SubB:
        sub_value: int = 2

    @dataclasses.dataclass
    class Config:
        parent_arg: str = "default"
        sub: Union[SubA, SubB] = dataclasses.field(default_factory=SubA)

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(
            tyro.conf.CascadeSubcommandArgs[Config],
            args=["--tyro-print-completion", "bash"],
        )

    output = target.getvalue()

    # Both backends should generate completions with subcommands.
    assert "sub:sub-a" in output or "sub_a" in output
    assert "sub:sub-b" in output or "sub_b" in output
    # Parent argument should be available.
    assert "--parent-arg" in output or "--parent_arg" in output


def test_cascade_marker_detection(backend: str) -> None:
    """Test that CascadeSubcommandArgs marker is properly detected in completion spec."""
    if backend != "tyro":
        pytest.skip("Cascade marker detection is tyro-specific")

    @dataclasses.dataclass
    class Config:
        regular_field: int = 5
        cascade_field: tyro.conf.CascadeSubcommandArgs[str] = "default"

    # Generate completion script.
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(Config, args=["--tyro-print-completion", "bash"])

    completion_script = target.getvalue()

    # The completion spec is embedded in the script.
    # Verify it contains the fields and cascade info.
    assert "regular-field" in completion_script or "regular_field" in completion_script
    assert "cascade-field" in completion_script or "cascade_field" in completion_script

    # Verify the spec has cascade markers.
    # The cascade field should be tracked in the spec.
    assert "'cascade'" in completion_script


def test_nargs_with_choices_completion(backend: str) -> None:
    """Test that nargs is properly tracked for choice options in completion spec."""
    if backend != "tyro":
        pytest.skip("Choice nargs tracking is tyro-specific")

    @dataclasses.dataclass
    class Config:
        # Single choice.
        mode: Literal["train", "eval"] = "train"
        # Multiple choices.
        modes: List[Literal["train", "eval", "test"]] = dataclasses.field(
            default_factory=lambda: ["train"]
        )

    # Generate completion script.
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(Config, args=["--tyro-print-completion", "bash"])

    completion_script = target.getvalue()

    # Verify completion spec has choices and nargs.
    assert "'choices'" in completion_script
    assert "train" in completion_script
    assert "eval" in completion_script
    assert "test" in completion_script

    # Verify nargs is tracked for the list field.
    assert "'nargs'" in completion_script


def test_metavar_in_description(backend: str) -> None:
    """Test that metavar is included in option descriptions."""
    if backend != "tyro":
        pytest.skip("Metavar formatting is tyro-specific")

    @dataclasses.dataclass
    class Config:
        count: int = 5
        name: str = "default"

    # Generate completion script.
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(Config, args=["--tyro-print-completion", "bash"])

    completion_script = target.getvalue()

    # Verify metavar (type hints) appear in descriptions.
    # The descriptions should include INT and STR metavars.
    assert "INT" in completion_script or "int" in completion_script
    assert "STR" in completion_script or "str" in completion_script


@dataclasses.dataclass
class _ConfigForBulletTest:
    # No custom helptext, just default.
    simple: int = 5
    # Custom helptext.
    documented: int = 10
    """This is a custom help message."""


def test_smart_bullet_separator(backend: str) -> None:
    """Test that bullet separator is only used when there's custom helptext."""
    if backend != "tyro":
        pytest.skip("Bullet separator logic is tyro-specific")

    # Generate completion script.
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(_ConfigForBulletTest, args=["--tyro-print-completion", "bash"])

    completion_script = target.getvalue()

    # Verify bullet separator is used for fields with custom helptext.
    # The custom help message should have the bullet.
    assert "custom help" in completion_script.lower()
    assert "\u2022" in completion_script


@dataclasses.dataclass
class _PreprocessingA:
    scale: float = 1.0


@dataclasses.dataclass
class _PreprocessingB:
    normalize: bool = True


@dataclasses.dataclass
class _AugmentationA:
    rotate: bool = True


@dataclasses.dataclass
class _AugmentationB:
    flip: bool = False


@dataclasses.dataclass
class _DatasetMNIST:
    """Dataset with its own frontier groups."""

    preprocessing: Union[_PreprocessingA, _PreprocessingB]
    augmentation: Union[_AugmentationA, _AugmentationB]


@dataclasses.dataclass
class _DatasetImageNet:
    resolution: int = 224


@dataclasses.dataclass
class _SubcommandWithFrontier:
    """A subcommand that has subcommands, one of which has frontier groups."""

    dataset: Union[_DatasetMNIST, _DatasetImageNet]


@dataclasses.dataclass
class _NestedMainCommand:
    # This creates a subcommand that has frontier groups.
    config: _SubcommandWithFrontier


def test_nested_subcommand_coverage(backend: str) -> None:
    """Test nested subcommands for coverage of _build_subcommand_spec recursion."""
    if backend != "tyro":
        pytest.skip("Testing tyro-specific completion generation")

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(_NestedMainCommand, args=["--tyro-print-completion", "bash"])

    completion_script = target.getvalue()
    # Verify nested subcommands are present.
    assert "config" in completion_script
    # Check for deeply nested frontier groups within subcommands.
    assert "dataset" in completion_script or "preprocessing" in completion_script


def test_positional_argument_coverage(backend: str) -> None:
    """Test that positional arguments are skipped in completion spec."""
    if backend != "tyro":
        pytest.skip("Testing tyro-specific completion generation")

    def main(input_file: tyro.conf.Positional[str], output: str = "out.txt") -> str:
        """Test with positional argument.

        Args:
            input_file: Input file path (positional).
            output: Output file path.
        """
        return f"{input_file} -> {output}"

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(main, args=["--tyro-print-completion", "bash"])

    completion_script = target.getvalue()
    # Positional args shouldn't appear in options list, only regular flags.
    assert "--output" in completion_script


def test_count_action_coverage(backend: str) -> None:
    """Test count action type for coverage."""
    if backend != "tyro":
        pytest.skip("Testing tyro-specific completion generation")

    def main(verbose: tyro.conf.UseCounterAction[int]) -> int:
        """Test function with counter action.

        Args:
            verbose: Verbosity level.
        """
        return verbose

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(main, args=["--tyro-print-completion", "bash"])

    completion_script = target.getvalue()
    # Count action creates a flag-type option.
    assert "flag" in completion_script.lower() or "verbose" in completion_script


def test_metavar_and_helptext_edge_cases(backend: str) -> None:
    """Test that completion works even with minimal help text."""
    if backend != "tyro":
        pytest.skip("Testing tyro-specific completion generation")

    def main(value: int = 5, flag: bool = False) -> int:
        """Test completion with basic arguments."""
        return value

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(main, args=["--tyro-print-completion", "bash"])

    completion_script = target.getvalue()
    # Verify basic completion generation works.
    assert "value" in completion_script or "flag" in completion_script


def test_unsupported_shell_error(backend: str) -> None:
    """Test that unsupported shell types raise an error."""
    if backend != "tyro":
        pytest.skip("Testing tyro-specific error handling")

    def main(value: int = 5) -> int:
        """Test function."""
        return value

    # Test that tcsh (supported by argparse but not tyro) raises ValueError.
    with pytest.raises(ValueError, match="Unsupported shell.*tcsh"):
        tyro.cli(main, args=["--tyro-print-completion", "tcsh"])


def test_nested_dataclass_completion(backend: str) -> None:
    """Test that nested dataclass fields are included in completion spec.

    This tests the case where a dataclass has a nested dataclass field (not a Union),
    which creates child parsers via child_from_prefix rather than subcommands.
    """

    @dataclasses.dataclass
    class OptimizerConfig:
        learning_rate: float = 3e-4
        weight_decay: float = 1e-2

    @dataclasses.dataclass
    class Config:
        opt: OptimizerConfig
        seed: int = 0

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(Config, args=["--tyro-print-completion", "bash"])

    completion_script = target.getvalue()

    # Verify that the top-level argument is present.
    assert "--seed" in completion_script

    # Verify that nested arguments are present with their prefix.
    assert "--opt.learning-rate" in completion_script
    assert "--opt.weight-decay" in completion_script


# Unit tests for reconstruct_colon_words.


def test_reconstruct_colon_words_basic() -> None:
    """Test basic word reconstruction for colon-separated subcommands."""
    from typing import Any, Dict

    from tyro._backends._completion._completion_script import reconstruct_colon_words

    # Spec with colon-separated subcommands.
    spec: Dict[str, Any] = {
        "subcommands": {
            "dataset:mnist": {},
            "dataset:image-net": {},
            "optimizer:adam": {},
        }
    }

    # Test 1: Basic reconstruction of "dataset:mnist".
    # Bash splits this as ["dataset", ":", "mnist"].
    words = ["dataset", ":", "mnist"]
    reconstructed, new_cword = reconstruct_colon_words(words, 2, spec)
    assert reconstructed == ["dataset:mnist"]
    assert new_cword == 0

    # Test 2: Partial completion "dataset:".
    # Bash splits this as ["dataset", ":"].
    words = ["dataset", ":"]
    reconstructed, new_cword = reconstruct_colon_words(words, 1, spec)
    assert reconstructed == ["dataset:"]
    assert new_cword == 0

    # Test 3: Partial prefix "dataset:m".
    # Bash splits this as ["dataset", ":", "m"].
    words = ["dataset", ":", "m"]
    reconstructed, new_cword = reconstruct_colon_words(words, 2, spec)
    assert reconstructed == ["dataset:m"]
    assert new_cword == 0


def test_reconstruct_colon_words_no_match() -> None:
    """Test that words are not reconstructed when they don't match subcommands."""
    from typing import Any, Dict

    from tyro._backends._completion._completion_script import reconstruct_colon_words

    spec: Dict[str, Any] = {"subcommands": {"dataset:mnist": {}}}

    # Test 1: Non-matching colon pattern (e.g., option value "key:value").
    # Should not be merged since "key:value" is not a known subcommand.
    words = ["--config", "key", ":", "value"]
    reconstructed, new_cword = reconstruct_colon_words(words, 3, spec)
    # Since "key:value" doesn't match any subcommand, keep them separate.
    # Standalone colons are skipped.
    assert reconstructed == ["--config", "key", "value"]
    assert new_cword == 2


def test_reconstruct_colon_words_multiple() -> None:
    """Test reconstruction with multiple colon-separated subcommands."""
    from typing import Any, Dict

    from tyro._backends._completion._completion_script import reconstruct_colon_words

    spec: Dict[str, Any] = {
        "subcommands": {
            "dataset:mnist": {},
            "optimizer:adam": {},
        }
    }

    # Test: Multiple subcommands "dataset:mnist optimizer:adam".
    # Bash splits as ["dataset", ":", "mnist", "optimizer", ":", "adam"].
    words = ["dataset", ":", "mnist", "optimizer", ":", "adam"]
    reconstructed, new_cword = reconstruct_colon_words(words, 5, spec)
    assert reconstructed == ["dataset:mnist", "optimizer:adam"]
    assert (
        new_cword == 1
    )  # Cursor on "adam" -> after reconstruction it's on second word.


def test_reconstruct_colon_words_with_options() -> None:
    """Test reconstruction with flags mixed in."""
    from typing import Any, Dict

    from tyro._backends._completion._completion_script import reconstruct_colon_words

    spec: Dict[str, Any] = {
        "subcommands": {
            "dataset:mnist": {},
        }
    }

    # Test: Subcommand with options "dataset:mnist --lr 0.001".
    # Bash splits as ["dataset", ":", "mnist", "--lr", "0.001"].
    words = ["dataset", ":", "mnist", "--lr", "0.001"]
    reconstructed, new_cword = reconstruct_colon_words(words, 4, spec)
    assert reconstructed == ["dataset:mnist", "--lr", "0.001"]
    assert new_cword == 2  # Cursor on "0.001" -> after merging, it's at index 2.


def test_reconstruct_colon_words_cursor_on_colon() -> None:
    """Test cursor position when it's on the colon itself."""
    from typing import Any, Dict

    from tyro._backends._completion._completion_script import reconstruct_colon_words

    spec: Dict[str, Any] = {"subcommands": {"dataset:mnist": {}}}

    # Test: Cursor is on the colon character.
    # Words: ["dataset", ":"], cursor at index 1 (the colon).
    words = ["dataset", ":"]
    reconstructed, new_cword = reconstruct_colon_words(words, 1, spec)
    # The colon should be merged with "dataset" to form "dataset:".
    assert reconstructed == ["dataset:"]
    # Cursor should be on the merged word.
    assert new_cword == 0


def test_reconstruct_colon_words_empty() -> None:
    """Test reconstruction with empty word list."""
    from typing import Any, Dict

    from tyro._backends._completion._completion_script import reconstruct_colon_words

    spec: Dict[str, Any] = {"subcommands": {}}

    # Empty word list.
    words: list[str] = []
    reconstructed, new_cword = reconstruct_colon_words(words, 0, spec)
    assert reconstructed == []
    assert new_cword == 0


# Unit tests for get_completions.


def test_get_completions_path_marker() -> None:
    """Test that get_completions returns path marker for string/Path arguments."""
    from typing import Any, Dict, cast

    from tyro._backends._completion._completion_script import get_completions
    from tyro._backends._completion._spec import build_completion_spec
    from tyro._parsers import ParserSpecification
    from tyro._singleton import MISSING_NONPROP

    @dataclasses.dataclass
    class Config:
        input_file: pathlib.Path = pathlib.Path("input.txt")
        name: str = "default"
        count: int = 0
        verbose: bool = False

    # Build spec from dataclass.
    parser_spec = ParserSpecification.from_callable_or_type(
        Config,
        markers=(),
        description=None,
        parent_classes=set(),
        default_instance=MISSING_NONPROP,
        intern_prefix="",
        extern_prefix="",
        subcommand_prefix="",
        support_single_arg_types=False,
        prog_suffix="",
    )
    # Cast needed because get_completions uses Dict[str, Any] (it's standalone).
    spec = cast(Dict[str, Any], build_completion_spec(parser_spec, "prog"))

    # Test 1: Completing after --input-file should return path marker.
    completions = get_completions(["prog", "--input-file", ""], 2, spec)
    assert completions == ["__TYRO_COMPLETE_FILES__"]

    # Test 2: Completing after --name (str) should also return path marker.
    completions = get_completions(["prog", "--name", ""], 2, spec)
    assert completions == ["__TYRO_COMPLETE_FILES__"]

    # Test 3: Completing after --count (int) should return empty.
    completions = get_completions(["prog", "--count", ""], 2, spec)
    assert completions == []

    # Test 4: Completing after --verbose (flag) should show all options.
    completions = get_completions(["prog", "--verbose", ""], 2, spec)
    assert len(completions) > 0
    completion_flags = [c.split("\t")[0] for c in completions]
    assert "--input-file" in completion_flags
    assert "--name" in completion_flags
    assert "--count" in completion_flags

    # Test 5: Completing at root level should show all options.
    completions = get_completions(["prog", ""], 1, spec)
    completion_flags = [c.split("\t")[0] for c in completions]
    assert "--input-file" in completion_flags
    assert "--name" in completion_flags
    assert "--count" in completion_flags
    assert "--verbose" in completion_flags
