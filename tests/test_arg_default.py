from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Union

from typing_extensions import Annotated

import tyro


def test_arg_default() -> None:
    """Test that tyro.conf.arg(default=) is used when field has no default."""

    @dataclass
    class Config:
        # Field with no default, arg default is used.
        no_field_default: Annotated[int, tyro.conf.arg(default=100)]

        # Regular field with default.
        regular: int = 1

        # Field with default that takes precedence over arg default.
        field_precedence: Annotated[int, tyro.conf.arg(default=42)] = 2

        # Optional field with None default.
        opt: Annotated[Optional[str], tyro.conf.arg(default="hello")] = None

    # Test with no args.
    config = tyro.cli(Config, args=[])
    assert config.regular == 1  # Field default.
    assert config.field_precedence == 2  # Field default takes precedence.
    assert config.opt is None  # Field default takes precedence.
    assert config.no_field_default == 100  # Arg default used when field has no default.

    # Test with args.
    config = tyro.cli(
        Config,
        args=[
            "--regular",
            "5",
            "--field-precedence",
            "10",
            "--opt",
            "world",
            "--no-field-default",
            "200",
        ],
    )
    assert config.regular == 5  # CLI value.
    assert config.field_precedence == 10  # CLI value overrides field default.
    assert config.opt == "world"  # CLI value overrides field default.
    assert config.no_field_default == 200  # CLI value overrides arg default.


def test_arg_default_with_help() -> None:
    """Test that default values appear correctly in help text."""

    @dataclass
    class Config:
        # Field with no default, arg default is used.
        no_field_default: Annotated[int, tyro.conf.arg(default=100)]

        # Regular field with default.
        regular: int = 1

        # Field with default that takes precedence over arg default.
        field_precedence: Annotated[int, tyro.conf.arg(default=42)] = 2

    # Get help text by capturing stdout when --help is passed.
    import io
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        try:
            tyro.cli(Config, args=["--help"])
        except SystemExit:
            pass  # Expected to exit after printing help.

    help_text = f.getvalue()

    # Help text should show the field defaults when present, and arg defaults when no field default.
    assert "(default: 1)" in help_text
    assert "(default: 2)" in help_text  # Field default shown.
    assert (
        "(default: 42)" not in help_text
    )  # Arg default not shown when field default exists.
    assert "(default: 100)" in help_text  # Arg default shown for field with no default.


def test_arg_default_with_function() -> None:
    """Test that tyro.conf.arg(default=) works with functions too."""

    def func(
        no_default: Annotated[int, tyro.conf.arg(default=100)],
        regular: int = 1,
        field_precedence: Annotated[int, tyro.conf.arg(default=42)] = 2,
        opt: Annotated[Optional[str], tyro.conf.arg(default="hello")] = None,
    ) -> dict:
        return {
            "regular": regular,
            "field_precedence": field_precedence,
            "opt": opt,
            "no_default": no_default,
        }

    # Test with no args.
    result = tyro.cli(func, args=[])
    assert result["regular"] == 1  # Function default.
    assert result["field_precedence"] == 2  # Function default takes precedence.
    assert result["opt"] is None  # Function default takes precedence.
    assert (
        result["no_default"] == 100
    )  # Arg default used when parameter has no default.

    # Test with args.
    result = tyro.cli(
        func,
        args=[
            "--regular",
            "5",
            "--field-precedence",
            "10",
            "--opt",
            "world",
            "--no-default",
            "200",
        ],
    )
    assert result["regular"] == 5  # CLI value.
    assert result["field_precedence"] == 10  # CLI value overrides function default.
    assert result["opt"] == "world"  # CLI value overrides function default.
    assert result["no_default"] == 200  # CLI value overrides arg default.


def test_arg_default_with_immutable_types() -> None:
    """Test that tyro.conf.arg(default=) works with immutable complex types."""

    @dataclass
    class Config:
        # No default, use arg default for tuple (immutable).
        tuple_arg: Annotated[Tuple[int, str], tyro.conf.arg(default=(42, "hello"))]

        # Field default takes precedence over arg default.
        field_int: Annotated[int, tyro.conf.arg(default=100)] = 200

    # Test with no args.
    config = tyro.cli(Config, args=[])
    assert config.tuple_arg == (42, "hello")  # Arg default used.
    assert config.field_int == 200  # Field default takes precedence.

    # Test with args.
    config = tyro.cli(Config, args=["--tuple-arg", "99", "world"])
    assert config.tuple_arg == (99, "world")  # CLI value overrides arg default.


def test_arg_default_with_none() -> None:
    """Test that tyro.conf.arg(default=None) works properly."""

    @dataclass
    class Config:
        # No default, explicitly set to None via arg default.
        none_default: Annotated[Optional[str], tyro.conf.arg(default=None)]

        # Field default takes precedence over None arg default.
        field_default: Annotated[Optional[str], tyro.conf.arg(default=None)] = "value"

        # None field default takes precedence over arg default.
        none_field_default: Annotated[Optional[str], tyro.conf.arg(default="value")] = (
            None
        )

    # Test with no args.
    config = tyro.cli(Config, args=[])
    assert config.none_default is None  # None arg default used.
    assert config.field_default == "value"  # Field default takes precedence.
    assert config.none_field_default is None  # None field default takes precedence.


def test_arg_default_with_union_of_primitives() -> None:
    """Test that tyro.conf.arg(default=) works with union types of primitives."""

    @dataclass
    class Config:
        # No default, use arg default for Union of primitives.
        union_arg: Annotated[Union[int, str], tyro.conf.arg(default=42)]

        # Field default takes precedence over arg default.
        field_union: Annotated[Union[int, str], tyro.conf.arg(default=100)] = "string"

    # Test with no args.
    config = tyro.cli(Config, args=[])
    assert config.union_arg == 42  # Arg default used.
    assert config.field_union == "string"  # Field default takes precedence.

    # Test with args.
    config = tyro.cli(Config, args=["--union-arg", "hello", "--field-union", "50"])
    assert config.union_arg == "hello"  # CLI value overrides arg default.
    assert config.field_union == 50  # CLI value overrides field default.


def test_arg_default_with_other_arg_params() -> None:
    """Test that tyro.conf.arg(default=) can be used with other arg parameters."""

    @dataclass
    class Config:
        # No default, with custom name, help, and aliases.
        custom_arg: Annotated[
            int,
            tyro.conf.arg(
                name="custom", help="Custom help text.", aliases=("-c",), default=42
            ),
        ]

        # Field default takes precedence over arg default, but other params still apply.
        field_arg: Annotated[
            int,
            tyro.conf.arg(
                name="renamed", help="Help text.", metavar="NUMBER", default=100
            ),
        ] = 200

    # Test with no args.
    config = tyro.cli(Config, args=[])
    assert config.custom_arg == 42  # Arg default used.
    assert config.field_arg == 200  # Field default takes precedence.

    # Test with args using custom name and alias.
    config = tyro.cli(Config, args=["--custom", "50"])
    assert config.custom_arg == 50  # CLI value using custom name.

    config = tyro.cli(Config, args=["-c", "60"])
    assert config.custom_arg == 60  # CLI value using alias.

    config = tyro.cli(Config, args=["--renamed", "150"])
    assert config.field_arg == 150  # CLI value using renamed arg.
