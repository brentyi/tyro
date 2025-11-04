"""Tests for mutually exclusive argument groups."""

import dataclasses
from pathlib import Path
from typing import Literal, Optional, Tuple, Union

import pytest
from helptext_utils import get_helptext_with_checks
from typing_extensions import Annotated

import tyro


def test_required_mutex_group_basic() -> None:
    """Test basic required mutex group functionality."""
    RequiredGroup = tyro.conf.create_mutex_group(required=True)

    def main(
        option_a: Annotated[Union[str, None], RequiredGroup] = None,
        option_b: Annotated[Union[int, None], RequiredGroup] = None,
    ) -> Tuple[Optional[str], Optional[int]]:
        return option_a, option_b

    # Should work with just option_a.
    assert tyro.cli(main, args=["--option-a", "hello"]) == ("hello", None)

    # Should work with just option_b.
    assert tyro.cli(main, args=["--option-b", "42"]) == (None, 42)

    # Should fail when both are provided.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--option-a", "hello", "--option-b", "42"])

    # Should fail when neither is provided.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=[])


def test_optional_mutex_group_basic() -> None:
    """Test basic optional mutex group functionality."""
    OptionalGroup = tyro.conf.create_mutex_group(required=False)

    def main(
        verbose: Annotated[bool, OptionalGroup] = False,
        quiet: Annotated[bool, OptionalGroup] = False,
    ) -> Tuple[bool, bool]:
        return verbose, quiet

    # Should work with neither option.
    assert tyro.cli(main, args=[]) == (False, False)

    # Should work with just verbose.
    assert tyro.cli(main, args=["--verbose"]) == (True, False)

    # Should work with just quiet.
    assert tyro.cli(main, args=["--quiet"]) == (False, True)

    # Should fail when both are provided.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--verbose", "--quiet"])


def test_multiple_mutex_groups() -> None:
    """Test multiple independent mutex groups in the same function."""
    GroupA = tyro.conf.create_mutex_group(required=True)
    GroupB = tyro.conf.create_mutex_group(required=False)

    def main(
        option_a1: Annotated[Union[str, None], GroupA] = None,
        option_a2: Annotated[Union[str, None], GroupA] = None,
        option_b1: Annotated[bool, GroupB] = False,
        option_b2: Annotated[bool, GroupB] = False,
    ) -> Tuple[Optional[str], Optional[str], bool, bool]:
        return option_a1, option_a2, option_b1, option_b2

    # Should work with one from group A and one from group B.
    assert tyro.cli(main, args=["--option-a1", "test", "--option-b1"]) == (
        "test",
        None,
        True,
        False,
    )

    # Should work with one from group A and none from group B.
    assert tyro.cli(main, args=["--option-a2", "hello"]) == (
        None,
        "hello",
        False,
        False,
    )

    # Should fail with both from group A.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--option-a1", "a", "--option-a2", "b"])

    # Should fail with both from group B.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--option-a1", "test", "--option-b1", "--option-b2"])


def test_mutex_group_with_disallow_none() -> None:
    """Test mutex groups with DisallowNone configuration."""
    RequiredGroup = tyro.conf.create_mutex_group(required=True)

    def main(
        option_a: Annotated[Union[str, None], RequiredGroup] = None,
        option_b: Annotated[Union[int, None], RequiredGroup] = None,
    ) -> Tuple[Optional[str], Optional[int]]:
        return option_a, option_b

    # Regular values should work both with and without DisallowNone.
    assert tyro.cli(main, args=["--option-a", "hello"]) == ("hello", None)
    assert tyro.cli(
        main, args=["--option-a", "hello"], config=(tyro.conf.DisallowNone,)
    ) == ("hello", None)

    # DisallowNone prevents None from being passed via CLI.
    # Note: For string types, "None" is treated as the string "None", not the None value.
    # So this test validates that DisallowNone works with the mutex group feature.


def test_mutex_group_with_literal_types() -> None:
    """Test mutex groups with Literal types."""
    RequiredGroup = tyro.conf.create_mutex_group(required=True)

    def main(
        mode: Annotated[Optional[Literal["fast", "slow"]], RequiredGroup] = None,
        threads: Annotated[Union[int, None], RequiredGroup] = None,
    ) -> Tuple[Optional[str], Optional[int]]:
        return mode, threads

    # Should work with literal choices.
    assert tyro.cli(main, args=["--mode", "fast"]) == ("fast", None)
    assert tyro.cli(main, args=["--mode", "slow"]) == ("slow", None)

    # Should fail with invalid literal value.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--mode", "medium"])

    # Should work with the other option.
    assert tyro.cli(main, args=["--threads", "4"]) == (None, 4)


def test_mutex_group_with_path_types() -> None:
    """Test mutex groups with Path types."""
    RequiredGroup = tyro.conf.create_mutex_group(required=True)

    def main(
        input_file: Annotated[Optional[Path], RequiredGroup] = None,
        input_dir: Annotated[Optional[Path], RequiredGroup] = None,
    ) -> Tuple[Optional[Path], Optional[Path]]:
        return input_file, input_dir

    # Should work with file path.
    result = tyro.cli(main, args=["--input-file", "/tmp/test.txt"])
    assert result == (Path("/tmp/test.txt"), None)

    # Should work with directory path.
    result = tyro.cli(main, args=["--input-dir", "/home/user"])
    assert result == (None, Path("/home/user"))


def test_mutex_group_in_dataclass() -> None:
    """Test mutex groups within dataclass fields."""
    RequiredGroup = tyro.conf.create_mutex_group(required=True)
    OptionalGroup = tyro.conf.create_mutex_group(required=False)

    @dataclasses.dataclass
    class Config:
        # Required mutex group.
        option_a: Annotated[Union[str, None], RequiredGroup] = None
        option_b: Annotated[Union[int, None], RequiredGroup] = None
        # Optional mutex group.
        verbose: Annotated[bool, OptionalGroup] = False
        quiet: Annotated[bool, OptionalGroup] = False

    # Should work with valid combinations.
    config = tyro.cli(Config, args=["--option-a", "test", "--verbose"])
    assert config.option_a == "test"
    assert config.option_b is None
    assert config.verbose is True
    assert config.quiet is False

    # Should fail with invalid combinations.
    with pytest.raises(SystemExit):
        tyro.cli(Config, args=["--option-a", "a", "--option-b", "1"])

    with pytest.raises(SystemExit):
        tyro.cli(Config, args=["--option-a", "test", "--verbose", "--quiet"])


def test_mutex_group_helptext() -> None:
    """Test that mutex groups appear correctly in helptext."""
    RequiredGroup = tyro.conf.create_mutex_group(required=True)
    OptionalGroup = tyro.conf.create_mutex_group(required=False)

    def main(
        option_a: Annotated[Union[str, None], RequiredGroup] = None,
        option_b: Annotated[Union[int, None], RequiredGroup] = None,
        verbose: Annotated[bool, OptionalGroup] = False,
        quiet: Annotated[bool, OptionalGroup] = False,
    ) -> None:
        """Test function with mutex groups."""
        pass

    helptext = get_helptext_with_checks(main)

    # Check for mutually exclusive section markers.
    assert "mutually exclusive" in helptext.lower()

    # Check that required group is marked as required.
    assert "required" in helptext.lower()

    # Check that options are listed.
    assert "--option-a" in helptext
    assert "--option-b" in helptext
    assert "--verbose" in helptext
    assert "--quiet" in helptext


def test_mutex_group_with_flag_create_pairs_off() -> None:
    """Test mutex groups with FlagCreatePairsOff configuration."""
    OptionalGroup = tyro.conf.create_mutex_group(required=False)

    def main(
        verbose: Annotated[bool, OptionalGroup] = False,
        quiet: Annotated[bool, OptionalGroup] = False,
    ) -> Tuple[bool, bool]:
        return verbose, quiet

    # With FlagCreatePairsOff, only positive flags should be created.
    helptext = get_helptext_with_checks(main, config=(tyro.conf.FlagCreatePairsOff,))

    # Should have positive flags.
    assert "--verbose" in helptext
    assert "--quiet" in helptext

    # Should not have negative flags.
    assert "--no-verbose" not in helptext
    assert "--no-quiet" not in helptext

    # Functionality should still work.
    assert tyro.cli(
        main, args=["--verbose"], config=(tyro.conf.FlagCreatePairsOff,)
    ) == (True, False)


def test_three_way_mutex_group() -> None:
    """Test mutex group with three options."""
    RequiredGroup = tyro.conf.create_mutex_group(required=True)

    def main(
        option_a: Annotated[Union[str, None], RequiredGroup] = None,
        option_b: Annotated[Union[int, None], RequiredGroup] = None,
        option_c: Annotated[Union[float, None], RequiredGroup] = None,
    ) -> Tuple[Optional[str], Optional[int], Optional[float]]:
        return option_a, option_b, option_c

    # Should work with any single option.
    assert tyro.cli(main, args=["--option-a", "test"]) == ("test", None, None)
    assert tyro.cli(main, args=["--option-b", "42"]) == (None, 42, None)
    assert tyro.cli(main, args=["--option-c", "3.14"]) == (None, None, 3.14)

    # Should fail with any two options.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--option-a", "a", "--option-b", "1"])

    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--option-b", "1", "--option-c", "2.0"])

    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--option-a", "a", "--option-c", "2.0"])

    # Should fail with all three options.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--option-a", "a", "--option-b", "1", "--option-c", "2.0"])


def test_mutex_group_with_defaults_not_none() -> None:
    """Test mutex groups where defaults are not None."""
    OptionalGroup = tyro.conf.create_mutex_group(required=False)

    def main(
        verbose: Annotated[bool, OptionalGroup] = False,
        verbosity_level: Annotated[int, OptionalGroup] = 0,
    ) -> Tuple[bool, int]:
        return verbose, verbosity_level

    # Should use defaults when neither is specified.
    assert tyro.cli(main, args=[]) == (False, 0)

    # Should override one default.
    assert tyro.cli(main, args=["--verbose"]) == (True, 0)
    assert tyro.cli(main, args=["--verbosity-level", "2"]) == (False, 2)

    # Should fail when both are overridden.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--verbose", "--verbosity-level", "2"])


def test_mutex_group_on_dataclass_is_ignored() -> None:
    """Test that applying a mutex group annotation to a dataclass itself is ignored.

    This documents the current limitation where mutex groups can only be applied to
    individual fields, not to composite types like dataclasses. The MutexGroup
    annotation is ignored, and the dataclass behaves normally (creating subcommands
    for Optional[Dataclass] as usual).
    """
    MutexGroup = tyro.conf.create_mutex_group(required=True)

    @dataclasses.dataclass
    class Config:
        """A configuration dataclass."""

        foo: int = 1
        bar: str = "hello"

    def main(
        config: Annotated[
            Optional[Config], MutexGroup
        ] = None,  # MutexGroup annotation is ignored.
        other: Annotated[Optional[int], MutexGroup] = None,
    ) -> Tuple[Optional[Config], Optional[int]]:
        return config, other

    # The MutexGroup annotation on the dataclass is ignored for mutual exclusion.
    # Since config is Optional[Config], it creates subcommands as normal.

    # When only --other is provided, it works.
    result = tyro.cli(main, args=["--other", "42"])
    assert result == (None, 42)

    # Both --other and config:config can be used together since the MutexGroup
    # on config is ignored (they're not actually mutually exclusive).
    # Note: order matters due to subcommand parsing.
    result = tyro.cli(main, args=["--other", "42", "config:config"])
    assert result[0] is not None
    assert result[0].foo == 1
    assert result[0].bar == "hello"
    assert result[1] == 42


def test_nested_mutex_groups() -> None:
    """Test that mutex groups work correctly across nested dataclasses."""
    SharedGroup = tyro.conf.create_mutex_group(required=False)

    @dataclasses.dataclass
    class Inner:
        """Inner config."""

        option_a: Annotated[int, SharedGroup] = 1
        option_b: Annotated[int, SharedGroup] = 2

    @dataclasses.dataclass
    class Outer:
        """Outer config."""

        inner: Inner = dataclasses.field(default_factory=Inner)
        option_c: Annotated[int, SharedGroup] = 3
        option_d: Annotated[int, SharedGroup] = 4

    # Should use defaults when nothing is specified.
    config = tyro.cli(Outer, args=[])
    assert config.inner.option_a == 1
    assert config.inner.option_b == 2
    assert config.option_c == 3
    assert config.option_d == 4

    # Should allow overriding a single option.
    config = tyro.cli(Outer, args=["--option-c", "10"])
    assert config.option_c == 10
    assert config.option_d == 4
    assert config.inner.option_a == 1
    assert config.inner.option_b == 2

    # Should allow overriding a nested option.
    config = tyro.cli(Outer, args=["--inner.option-a", "20"])
    assert config.inner.option_a == 20
    assert config.inner.option_b == 2
    assert config.option_c == 3
    assert config.option_d == 4

    # Should fail when options from the same group are overridden, even across nesting levels.
    with pytest.raises(SystemExit):
        tyro.cli(Outer, args=["--option-c", "10", "--option-d", "20"])

    with pytest.raises(SystemExit):
        tyro.cli(Outer, args=["--inner.option-a", "10", "--inner.option-b", "20"])

    # Crucially, should fail when mixing options from different nesting levels.
    with pytest.raises(SystemExit):
        tyro.cli(Outer, args=["--option-c", "10", "--inner.option-a", "20"])

    with pytest.raises(SystemExit):
        tyro.cli(Outer, args=["--option-d", "10", "--inner.option-b", "20"])


def test_mutex_group_custom_title() -> None:
    """Test that custom titles appear correctly in helptext."""
    RequiredGroup = tyro.conf.create_mutex_group(required=True, title="output target")
    OptionalGroup = tyro.conf.create_mutex_group(
        required=False, title="verbosity level"
    )

    def main(
        option_a: Annotated[Union[str, None], RequiredGroup] = None,
        option_b: Annotated[Union[int, None], RequiredGroup] = None,
        verbose: Annotated[bool, OptionalGroup] = False,
        quiet: Annotated[bool, OptionalGroup] = False,
    ) -> None:
        """Test function with custom mutex group titles."""
        pass

    helptext = get_helptext_with_checks(main)

    # Check that custom titles appear in helptext.
    assert "output target" in helptext
    assert "verbosity level" in helptext

    # Check that default title does not appear.
    assert "mutually exclusive" not in helptext.lower()

    # Check that required group is still marked as required.
    assert "required" in helptext.lower()

    # Check that options are listed.
    assert "--option-a" in helptext
    assert "--option-b" in helptext
    assert "--verbose" in helptext
    assert "--quiet" in helptext

    # Verify functionality still works - mutual exclusion is enforced.
    assert tyro.cli(main, args=["--option-a", "test"]) is None
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--option-a", "test", "--option-b", "42"])
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--verbose", "--quiet"])


def test_mutex_group_custom_title_multiple_groups() -> None:
    """Test multiple independent mutex groups with different custom titles."""
    GroupA = tyro.conf.create_mutex_group(required=True, title="input source")
    GroupB = tyro.conf.create_mutex_group(required=False, title="output format")
    GroupC = tyro.conf.create_mutex_group(required=False, title="logging options")

    def main(
        input_file: Annotated[Union[str, None], GroupA] = None,
        input_url: Annotated[Union[str, None], GroupA] = None,
        format_json: Annotated[bool, GroupB] = False,
        format_yaml: Annotated[bool, GroupB] = False,
        log_verbose: Annotated[bool, GroupC] = False,
        log_quiet: Annotated[bool, GroupC] = False,
    ) -> None:
        """Test function with multiple custom mutex group titles."""
        pass

    helptext = get_helptext_with_checks(main)

    # Check that all custom titles appear in helptext.
    assert "input source" in helptext
    assert "output format" in helptext
    assert "logging options" in helptext

    # Check that default title does not appear.
    assert "mutually exclusive" not in helptext.lower()

    # Verify that each group works independently.
    assert tyro.cli(main, args=["--input-file", "test.txt", "--format-json"]) is None
    assert tyro.cli(main, args=["--input-url", "http://example.com"]) is None

    # Verify mutual exclusion within each group.
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--input-file", "test.txt", "--input-url", "url"])
    with pytest.raises(SystemExit):
        tyro.cli(
            main, args=["--input-file", "test.txt", "--format-json", "--format-yaml"]
        )
    with pytest.raises(SystemExit):
        tyro.cli(
            main, args=["--input-file", "test.txt", "--log-verbose", "--log-quiet"]
        )
