"""Tests for `tyro.conf.subcommand(aliases=..., is_default=...)` and the
matching SubcommandApp features (aliases, help override, default handler,
nested apps)."""

from __future__ import annotations

import contextlib
import dataclasses
import io
from dataclasses import dataclass
from typing import Any, Union, cast

import pytest
from typing_extensions import Annotated

import tyro
from tyro.extras import SubcommandApp

# --------------------------------------------------------------------------- #
# Core: tyro.conf.subcommand(aliases=..., is_default=...)                      #
# --------------------------------------------------------------------------- #


@dataclass
class _A:
    x: int = 1


@dataclass
class _B:
    y: int = 2


@dataclass
class _Leaf1:
    z: int = 0


@dataclass
class _Leaf2:
    z: int = 0


@dataclass
class _Inner1:
    leaf: Union[
        Annotated[_Leaf1, tyro.conf.subcommand("alpha", aliases=["a"])],
        Annotated[_Leaf2, tyro.conf.subcommand("beta", aliases=["b"])],
    ]


@dataclass
class _Inner2:
    z: int = 0


@dataclass
class _OuterWithNestedAliases:
    inner: Union[
        Annotated[_Inner1, tyro.conf.subcommand("one", aliases=["1"])],
        Annotated[_Inner2, tyro.conf.subcommand("two", aliases=["2"])],
    ]


def test_subcommand_alias_resolves_to_canonical():
    result = tyro.cli(
        cast(
            Any,
            Union[
                Annotated[_A, tyro.conf.subcommand("aa", aliases=["a", "alpha"])],
                Annotated[_B, tyro.conf.subcommand("bb")],
            ],
        ),
        args=["alpha", "--x", "5"],
    )
    assert result == _A(x=5)


def test_subcommand_canonical_still_works_with_aliases():
    result = tyro.cli(
        cast(
            Any,
            Union[
                Annotated[_A, tyro.conf.subcommand("aa", aliases=["a"])],
                Annotated[_B, tyro.conf.subcommand("bb")],
            ],
        ),
        args=["aa", "--x", "9"],
    )
    assert result == _A(x=9)


def test_subcommand_alias_appears_in_help(capsys):
    with pytest.raises(SystemExit):
        tyro.cli(
            cast(
                Any,
                Union[
                    Annotated[_A, tyro.conf.subcommand("aa", aliases=["a", "alpha"])],
                    Annotated[_B, tyro.conf.subcommand("bb")],
                ],
            ),
            args=["--help"],
        )
    out = capsys.readouterr().out
    # Both the canonical name and at least one alias should be visible.
    assert "aa" in out
    assert "alpha" in out


def test_subcommand_alias_must_not_start_with_hyphen():
    with pytest.raises(AssertionError):
        tyro.conf.subcommand("aa", aliases=["-a"])


def test_subcommand_is_default_no_args():
    """is_default makes a branch the default when no subcommand is given."""
    result = tyro.cli(
        cast(
            Any,
            Union[
                Annotated[_A, tyro.conf.subcommand("aa", is_default=True)],
                Annotated[_B, tyro.conf.subcommand("bb")],
            ],
        ),
        args=[],
    )
    assert result == _A(x=1)


def test_subcommand_is_default_explicit_other():
    result = tyro.cli(
        cast(
            Any,
            Union[
                Annotated[_A, tyro.conf.subcommand("aa", is_default=True)],
                Annotated[_B, tyro.conf.subcommand("bb")],
            ],
        ),
        args=["bb", "--y", "42"],
    )
    assert result == _B(y=42)


def test_subcommand_multiple_is_default_raises():
    with pytest.raises(AssertionError):
        tyro.cli(
            cast(
                Any,
                Union[
                    Annotated[_A, tyro.conf.subcommand("aa", is_default=True)],
                    Annotated[_B, tyro.conf.subcommand("bb", is_default=True)],
                ],
            ),
            args=[],
        )


# --------------------------------------------------------------------------- #
# Argparse-backend scanner helpers (defensive branches)                        #
# --------------------------------------------------------------------------- #


def test_find_subcommand_token_skips_double_dash_and_unknowns():
    """Cover defensive branches in the argparse-backend token scanner:
    the `--` separator skip, and the "no match, keep scanning" increment."""
    from tyro._backends._argparse_backend import _find_subcommand_token

    choices = {"aa", "bb"}
    # `--` is skipped; no subcommand follows.
    assert _find_subcommand_token(["--"], 0, choices) is None
    # Non-flag, non-choice token: scanner walks past it.
    assert _find_subcommand_token(["unknown"], 0, choices) is None
    # `--` then a real subcommand still resolves.
    assert _find_subcommand_token(["--", "aa"], 0, choices) == 1


def test_is_default_inner_subparser_without_default_breaks():
    """Outer subcommand uses is_default=True; inner subparser has no
    is_default and the user provided no inner selection. The argparse
    shim should walk in, fail to find/inject for the inner level, and
    stop walking — argparse then reports the missing subcommand."""

    @dataclass
    class Outer1:
        inner: Union[
            Annotated[_Leaf1, tyro.conf.subcommand("leaf1")],
            Annotated[_Leaf2, tyro.conf.subcommand("leaf2")],
        ]

    @dataclass
    class Outer2:
        z: int = 0

    with pytest.raises(SystemExit):
        tyro.cli(
            cast(
                Any,
                Union[
                    Annotated[Outer1, tyro.conf.subcommand("outer1", is_default=True)],
                    Annotated[Outer2, tyro.conf.subcommand("outer2")],
                ],
            ),
            args=[],
        )


# --------------------------------------------------------------------------- #
# SubcommandApp                                                                #
# --------------------------------------------------------------------------- #


def test_subcommandapp_aliases(capsys):
    app = SubcommandApp()

    @app.command(aliases=["sum", "+"])
    def add(a: int, b: int) -> None:
        print(f"{a}+{b}={a + b}")

    app.cli(args=["sum", "--a", "1", "--b", "2"])
    assert capsys.readouterr().out.strip() == "1+2=3"

    app.cli(args=["+", "--a", "4", "--b", "5"])
    assert capsys.readouterr().out.strip() == "4+5=9"

    app.cli(args=["add", "--a", "7", "--b", "8"])
    assert capsys.readouterr().out.strip() == "7+8=15"


def test_subcommandapp_help_override(capsys):
    app = SubcommandApp()

    @app.command(help="Override help text!")
    def foo() -> None:
        """The original docstring."""
        pass

    @app.command
    def bar() -> None:
        pass

    with pytest.raises(SystemExit):
        app.cli(args=["--help"])
    out = capsys.readouterr().out
    assert "Override help text!" in out
    assert "The original docstring." not in out


def test_subcommandapp_is_default(capsys):
    """A command marked is_default=True is selected when no subcommand is named."""
    app = SubcommandApp()

    @app.command(is_default=True)
    def run(name: str = "world") -> None:
        print(f"hello {name}")

    @app.command
    def other() -> None:
        print("other!")

    app.cli(args=[])
    assert capsys.readouterr().out.strip() == "hello world"

    app.cli(args=["--name", "alice"])
    assert capsys.readouterr().out.strip() == "hello alice"

    # Explicit invocation of the default subcommand still works.
    app.cli(args=["run", "--name", "bob"])
    assert capsys.readouterr().out.strip() == "hello bob"

    app.cli(args=["other"])
    assert capsys.readouterr().out.strip() == "other!"


def test_subcommandapp_double_is_default_raises():
    app = SubcommandApp()

    @app.command(is_default=True)
    def first() -> None:
        pass

    with pytest.raises(AssertionError):

        @app.command(is_default=True)
        def second() -> None:
            pass


def test_subcommandapp_nested(capsys):
    db = SubcommandApp()

    @db.command
    def migrate(version: int = 1) -> None:
        print(f"migrating to {version}")

    @db.command
    def seed(rows: int = 10) -> None:
        print(f"seeding {rows} rows")

    app = SubcommandApp()
    app.command(db, name="db")

    @app.command
    def hello(name: str = "world") -> None:
        print(f"hello {name}")

    app.cli(args=["db", "migrate", "--version", "7"])
    assert capsys.readouterr().out.strip() == "migrating to 7"

    app.cli(args=["db", "seed", "--rows", "5"])
    assert capsys.readouterr().out.strip() == "seeding 5 rows"

    app.cli(args=["hello", "--name", "tyro"])
    assert capsys.readouterr().out.strip() == "hello tyro"


def test_subcommandapp_nested_with_aliases(capsys):
    db = SubcommandApp()

    @db.command(aliases=["m"])
    def migrate(version: int = 1) -> None:
        print(f"migrating to {version}")

    app = SubcommandApp()
    app.command(db, name="db", aliases=["database"])

    app.cli(args=["db", "m", "--version", "3"])
    assert capsys.readouterr().out.strip() == "migrating to 3"

    app.cli(args=["database", "migrate"])
    assert capsys.readouterr().out.strip() == "migrating to 1"

    app.cli(args=["database", "m"])
    assert capsys.readouterr().out.strip() == "migrating to 1"


def test_sort_subcommands_does_not_persist_across_cli_calls(capsys):
    """Calling cli(sort_subcommands=True) must not mutate the registration order."""
    app = SubcommandApp()

    @app.command
    def zeta() -> None:
        pass

    @app.command
    def alpha() -> None:
        pass

    with pytest.raises(SystemExit):
        app.cli(args=["--help"], sort_subcommands=True)
    sorted_out = capsys.readouterr().out
    sorted_idx_a = sorted_out.index("alpha")
    sorted_idx_z = sorted_out.index("zeta")
    assert sorted_idx_a < sorted_idx_z

    with pytest.raises(SystemExit):
        app.cli(args=["--help"], sort_subcommands=False)
    unsorted_out = capsys.readouterr().out
    unsorted_idx_a = unsorted_out.index("alpha")
    unsorted_idx_z = unsorted_out.index("zeta")
    # Registration order: zeta first.
    assert unsorted_idx_z < unsorted_idx_a


def test_is_default_inconsistent_with_field_default_raises():
    """If is_default=True is set on one branch but the field default
    matches another, we should error rather than silently picking one."""

    @dataclass
    class Wrap:
        cmd: Union[
            Annotated[_A, tyro.conf.subcommand("aa")],
            Annotated[_B, tyro.conf.subcommand("bb", is_default=True)],
        ] = dataclasses.field(default_factory=lambda: _A(x=3))

    with pytest.raises(AssertionError):
        tyro.cli(Wrap, args=[])


def test_inject_default_skips_flag_values():
    """A flag value that happens to equal a subcommand name must not be
    mistaken for an explicit subcommand selection."""

    @dataclass
    class A2:
        # Required arg whose value `bb` collides with subcommand name `bb`.
        msg: str

    @dataclass
    class B2:
        y: int = 0

    # is_default selects A2; user passes --msg bb. The "bb" should be
    # consumed by --msg, not treated as choosing the B2 subcommand.
    result = tyro.cli(
        cast(
            Any,
            Union[
                Annotated[A2, tyro.conf.subcommand("aa", is_default=True)],
                Annotated[B2, tyro.conf.subcommand("bb")],
            ],
        ),
        args=["--msg", "bb"],
    )
    assert result == A2(msg="bb")


def test_completion_includes_aliases(capsys):
    """Shell completion output should list aliases as selectable subcommands."""
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(
            cast(
                Any,
                Union[
                    Annotated[_A, tyro.conf.subcommand("aa", aliases=["alpha"])],
                    Annotated[_B, tyro.conf.subcommand("bb", aliases=["beta"])],
                ],
            ),
            args=["--tyro-print-completion", "bash"],
        )
    script = target.getvalue()
    assert "aa" in script and "alpha" in script
    assert "bb" in script and "beta" in script


def test_completion_includes_nested_aliases():
    """Aliases on subcommands nested under another subcommand should also
    appear in completion output (covers the recursive _build_subcommand_spec
    alias-emission path)."""
    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(_OuterWithNestedAliases, args=["--tyro-print-completion", "bash"])
    script = target.getvalue()
    assert "one" in script and "two" in script
    # Aliases should also be listed.
    assert "'1'" in script or " 1 " in script
    assert "'2'" in script or " 2 " in script


def test_alias_help_shows_canonical(capsys):
    """Invoking the CLI with `<alias> --help` should produce help for the
    canonical subcommand (argparse routes via the underlying parser, which
    is keyed by canonical name)."""
    with pytest.raises(SystemExit):
        tyro.cli(
            cast(
                Any,
                Union[
                    Annotated[_A, tyro.conf.subcommand("aa", aliases=["alpha"])],
                    Annotated[_B, tyro.conf.subcommand("bb")],
                ],
            ),
            args=["alpha", "--help"],
        )
    out = capsys.readouterr().out
    # Help should describe the chosen branch's args.
    assert "--x" in out


def test_alias_collides_with_canonical_in_same_union():
    """If an alias on one branch matches the canonical name of another, the
    canonical wins (argparse rejects the alias as a duplicate; tyro backend
    resolves to canonical first via parser_from_name)."""
    # argparse raises ArgumentError on duplicate at parser construction.
    with pytest.raises(Exception):
        tyro.cli(
            cast(
                Any,
                Union[
                    Annotated[_A, tyro.conf.subcommand("aa", aliases=["bb"])],
                    Annotated[_B, tyro.conf.subcommand("bb")],
                ],
            ),
            args=["bb", "--y", "1"],
        )


def test_subcommandapp_three_level_nesting(capsys):
    """3-level deep SubcommandApp: app → group1 → group2 → command."""
    leaf = SubcommandApp()

    @leaf.command
    def deep(x: int = 0) -> None:
        print(f"deep {x}")

    mid = SubcommandApp()
    mid.command(leaf, name="leaf")

    app = SubcommandApp()
    app.command(mid, name="mid")

    app.cli(args=["mid", "leaf", "deep", "--x", "42"])
    assert capsys.readouterr().out.strip() == "deep 42"


# ---------- is_default × tyro.conf marker combinations ---------- #


def test_is_default_with_avoid_subcommands():
    """AvoidSubcommands collapses a Union with a default to a single
    parser. is_default=True provides that default, so the subcommand UI is
    dropped and only the default branch is reachable — consistent with
    AvoidSubcommands's documented behavior."""
    result = tyro.cli(
        cast(
            Any,
            Union[
                Annotated[_A, tyro.conf.subcommand("aa", is_default=True)],
                Annotated[_B, tyro.conf.subcommand("bb")],
            ],
        ),
        config=(tyro.conf.AvoidSubcommands,),
        args=["--x", "11"],
    )
    assert result == _A(x=11)


def test_is_default_with_new_subcommand_for_defaults():
    """NewSubcommandForDefaults synthesizes a 'default' subcommand only when
    a field default matches a branch. With is_default=True there is no field
    default, so this marker shouldn't synthesize anything extra."""
    result = tyro.cli(
        cast(
            Any,
            Union[
                Annotated[_A, tyro.conf.subcommand("aa", is_default=True)],
                Annotated[_B, tyro.conf.subcommand("bb")],
            ],
        ),
        config=(tyro.conf.NewSubcommandForDefaults,),
        args=[],
    )
    assert result == _A(x=1)


def test_is_default_with_consolidate_subcommand_args():
    """ConsolidateSubcommandArgs (alias of CascadeSubcommandArgs) lets args
    appear after all subcommand tokens. With is_default, an argument for the
    default branch should still resolve when no subcommand is named."""
    result = tyro.cli(
        cast(
            Any,
            Union[
                Annotated[_A, tyro.conf.subcommand("aa", is_default=True)],
                Annotated[_B, tyro.conf.subcommand("bb")],
            ],
        ),
        config=(tyro.conf.ConsolidateSubcommandArgs,),
        args=["--x", "11"],
    )
    assert result == _A(x=11)


def test_is_default_with_omit_subcommand_prefixes():
    """OmitSubcommandPrefixes only strips parent prefixes from subcommand
    names; orthogonal to is_default. Confirm both still work together."""

    @dataclass
    class Outer:
        cmd: Union[
            Annotated[_A, tyro.conf.subcommand("aa", is_default=True)],
            Annotated[_B, tyro.conf.subcommand("bb")],
        ]

    result = tyro.cli(
        Outer, config=(tyro.conf.OmitSubcommandPrefixes,), args=["aa", "--x", "3"]
    )
    assert result == Outer(cmd=_A(x=3))


def test_subcommandapp_nested_requires_name():
    sub = SubcommandApp()

    @sub.command
    def foo() -> None:
        pass

    app = SubcommandApp()
    with pytest.raises(AssertionError):
        app.command(sub)
