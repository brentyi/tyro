"""Tests for unions of Annotated types with subcommand_type_from_defaults constructors.

Tests that Annotated[T, tyro.conf.arg(constructor=subcommand_type_from_defaults(...))]
in a union correctly flattens inner subcommands into the outer union.
"""

import dataclasses
from typing import Union

from helptext_utils import get_helptext_with_checks
from typing_extensions import Annotated

import tyro


@dataclasses.dataclass(frozen=True)
class Config:
    name: str
    value: int


@dataclasses.dataclass(frozen=True)
class OptimizerA:
    lr: float = 0.01


@dataclasses.dataclass(frozen=True)
class OptimizerB:
    momentum: float = 0.9


@dataclasses.dataclass(frozen=True)
class PlainConfig:
    x: int = 0


@dataclasses.dataclass(frozen=True)
class Inner:
    name: str
    value: int


@dataclasses.dataclass(frozen=True)
class Outer:
    label: str
    inner: Union[
        Annotated[
            Inner,
            tyro.conf.arg(
                constructor=tyro.extras.subcommand_type_from_defaults(
                    {
                        "small": Inner(name="small", value=1),
                        "large": Inner(name="large", value=100),
                    }
                )
            ),
        ],
        Annotated[
            Inner,
            tyro.conf.arg(
                constructor=tyro.extras.subcommand_type_from_defaults(
                    {
                        "custom": Inner(name="custom", value=50),
                    }
                )
            ),
        ],
    ]


def test_basic_annotated_union() -> None:
    """Basic case: union of two annotated configs + None."""

    @dataclasses.dataclass(frozen=True)
    class Args:
        config: Union[
            Annotated[
                Config,
                tyro.conf.arg(
                    constructor=tyro.extras.subcommand_type_from_defaults(
                        {
                            "a": Config(name="a", value=1),
                            "b": Config(name="b", value=2),
                        }
                    )
                ),
            ],
            Annotated[
                Config,
                tyro.conf.arg(
                    constructor=tyro.extras.subcommand_type_from_defaults(
                        {
                            "c": Config(name="c", value=3),
                            "d": Config(name="d", value=4),
                        }
                    )
                ),
            ],
            None,
        ]

    # Verify all subcommands appear in help.
    helptext = get_helptext_with_checks(Args)
    assert "config:a" in helptext
    assert "config:b" in helptext
    assert "config:c" in helptext
    assert "config:d" in helptext
    assert "config:none" in helptext

    # Verify each subcommand parses correctly.
    assert tyro.cli(Args, args=["config:a"]) == Args(config=Config(name="a", value=1))
    assert tyro.cli(Args, args=["config:b"]) == Args(config=Config(name="b", value=2))
    assert tyro.cli(Args, args=["config:c"]) == Args(config=Config(name="c", value=3))
    assert tyro.cli(Args, args=["config:d"]) == Args(config=Config(name="d", value=4))
    assert tyro.cli(Args, args=["config:none"]) == Args(config=None)


def test_annotated_union_no_none() -> None:
    """Union of two annotated configs without None."""

    @dataclasses.dataclass(frozen=True)
    class Args:
        config: Union[
            Annotated[
                Config,
                tyro.conf.arg(
                    constructor=tyro.extras.subcommand_type_from_defaults(
                        {"x": Config(name="x", value=10)}
                    )
                ),
            ],
            Annotated[
                Config,
                tyro.conf.arg(
                    constructor=tyro.extras.subcommand_type_from_defaults(
                        {"y": Config(name="y", value=20)}
                    )
                ),
            ],
        ]

    assert tyro.cli(Args, args=["config:x"]) == Args(config=Config(name="x", value=10))
    assert tyro.cli(Args, args=["config:y"]) == Args(config=Config(name="y", value=20))


def test_annotated_union_single() -> None:
    """Single annotated config in a union with None."""

    @dataclasses.dataclass(frozen=True)
    class Args:
        config: Union[
            Annotated[
                Config,
                tyro.conf.arg(
                    constructor=tyro.extras.subcommand_type_from_defaults(
                        {
                            "p": Config(name="p", value=100),
                            "q": Config(name="q", value=200),
                        }
                    )
                ),
            ],
            None,
        ]

    helptext = get_helptext_with_checks(Args)
    assert "config:p" in helptext
    assert "config:q" in helptext
    assert "config:none" in helptext

    assert tyro.cli(Args, args=["config:p"]) == Args(config=Config(name="p", value=100))
    assert tyro.cli(Args, args=["config:q"]) == Args(config=Config(name="q", value=200))
    assert tyro.cli(Args, args=["config:none"]) == Args(config=None)


def test_annotated_union_with_override() -> None:
    """Test that subcommand defaults can be overridden via CLI args."""

    @dataclasses.dataclass(frozen=True)
    class Args:
        config: Union[
            Annotated[
                Config,
                tyro.conf.arg(
                    constructor=tyro.extras.subcommand_type_from_defaults(
                        {"first": Config(name="first", value=1)}
                    )
                ),
            ],
            Annotated[
                Config,
                tyro.conf.arg(
                    constructor=tyro.extras.subcommand_type_from_defaults(
                        {"second": Config(name="second", value=2)}
                    )
                ),
            ],
        ]

    result = tyro.cli(
        Args,
        args=["config:first", "--config.name", "custom", "--config.value", "99"],
    )
    assert result == Args(config=Config(name="custom", value=99))

    result = tyro.cli(
        Args,
        args=["config:second", "--config.name", "other", "--config.value", "42"],
    )
    assert result == Args(config=Config(name="other", value=42))


def test_annotated_union_different_types() -> None:
    """Union of annotated configs with different underlying types."""

    @dataclasses.dataclass(frozen=True)
    class TrainArgs:
        opt: Union[
            Annotated[
                OptimizerA,
                tyro.conf.arg(
                    constructor=tyro.extras.subcommand_type_from_defaults(
                        {
                            "adam": OptimizerA(lr=0.001),
                            "sgd-fast": OptimizerA(lr=0.1),
                        }
                    )
                ),
            ],
            Annotated[
                OptimizerB,
                tyro.conf.arg(
                    constructor=tyro.extras.subcommand_type_from_defaults(
                        {"heavy": OptimizerB(momentum=0.99)}
                    )
                ),
            ],
        ]

    assert tyro.cli(TrainArgs, args=["opt:adam"]) == TrainArgs(opt=OptimizerA(lr=0.001))
    assert tyro.cli(TrainArgs, args=["opt:sgd-fast"]) == TrainArgs(
        opt=OptimizerA(lr=0.1)
    )
    assert tyro.cli(TrainArgs, args=["opt:heavy"]) == TrainArgs(
        opt=OptimizerB(momentum=0.99)
    )


def test_annotated_union_three_groups() -> None:
    """Three groups of annotated configs in a union."""

    @dataclasses.dataclass(frozen=True)
    class Args:
        config: Union[
            Annotated[
                Config,
                tyro.conf.arg(
                    constructor=tyro.extras.subcommand_type_from_defaults(
                        {
                            "a1": Config(name="a1", value=1),
                            "a2": Config(name="a2", value=2),
                        }
                    )
                ),
            ],
            Annotated[
                Config,
                tyro.conf.arg(
                    constructor=tyro.extras.subcommand_type_from_defaults(
                        {"b1": Config(name="b1", value=3)}
                    )
                ),
            ],
            Annotated[
                Config,
                tyro.conf.arg(
                    constructor=tyro.extras.subcommand_type_from_defaults(
                        {
                            "c1": Config(name="c1", value=4),
                            "c2": Config(name="c2", value=5),
                            "c3": Config(name="c3", value=6),
                        }
                    )
                ),
            ],
        ]

    helptext = get_helptext_with_checks(Args)
    for name in (
        "config:a1",
        "config:a2",
        "config:b1",
        "config:c1",
        "config:c2",
        "config:c3",
    ):
        assert name in helptext

    assert tyro.cli(Args, args=["config:a1"]) == Args(config=Config(name="a1", value=1))
    assert tyro.cli(Args, args=["config:c3"]) == Args(config=Config(name="c3", value=6))


def test_annotated_union_mixed_with_plain_struct() -> None:
    """Mix of annotated config (with subcommand_type_from_defaults) and a plain struct type."""

    @dataclasses.dataclass(frozen=True)
    class Args:
        config: Union[
            Annotated[
                Config,
                tyro.conf.arg(
                    constructor=tyro.extras.subcommand_type_from_defaults(
                        {
                            "preset-a": Config(name="preset-a", value=1),
                            "preset-b": Config(name="preset-b", value=2),
                        }
                    )
                ),
            ],
            PlainConfig,
        ]

    helptext = get_helptext_with_checks(Args)
    assert "config:preset-a" in helptext
    assert "config:preset-b" in helptext
    assert "config:plain-config" in helptext

    assert tyro.cli(Args, args=["config:preset-a"]) == Args(
        config=Config(name="preset-a", value=1)
    )
    assert tyro.cli(Args, args=["config:plain-config", "--config.x", "42"]) == Args(
        config=PlainConfig(x=42)
    )


def test_annotated_union_nested_struct() -> None:
    """Annotated union inside a nested struct."""

    @dataclasses.dataclass(frozen=True)
    class Args:
        outer: Outer

    result = tyro.cli(Args, args=["--outer.label", "test", "outer.inner:small"])
    assert result == Args(outer=Outer(label="test", inner=Inner(name="small", value=1)))

    result = tyro.cli(Args, args=["--outer.label", "test", "outer.inner:custom"])
    assert result == Args(
        outer=Outer(label="test", inner=Inner(name="custom", value=50))
    )


def test_prefix_name_false_on_subcommands() -> None:
    """prefix_name=False on tyro.conf.arg() should remove the field prefix from subcommand names."""

    @dataclasses.dataclass(frozen=True)
    class Args:
        main: Annotated[
            Config,
            tyro.conf.arg(
                prefix_name=False,
                constructor=tyro.extras.subcommand_type_from_defaults(
                    {
                        "a": Config(name="a", value=1),
                        "b": Config(name="b", value=2),
                    }
                ),
            ),
        ]

    helptext = get_helptext_with_checks(Args)
    # Should be "a" and "b", not "main:a" and "main:b".
    assert "a" in helptext
    assert "b" in helptext
    assert "main:a" not in helptext
    assert "main:b" not in helptext

    assert tyro.cli(Args, args=["a"]) == Args(main=Config(name="a", value=1))
    assert tyro.cli(Args, args=["b"]) == Args(main=Config(name="b", value=2))


def test_prefix_name_false_with_annotated_union() -> None:
    """prefix_name=False combined with annotated union flattening."""

    @dataclasses.dataclass(frozen=True)
    class Args:
        config: Annotated[
            Union[
                Annotated[
                    Config,
                    tyro.conf.arg(
                        constructor=tyro.extras.subcommand_type_from_defaults(
                            {"x": Config(name="x", value=10)}
                        )
                    ),
                ],
                Annotated[
                    Config,
                    tyro.conf.arg(
                        constructor=tyro.extras.subcommand_type_from_defaults(
                            {"y": Config(name="y", value=20)}
                        )
                    ),
                ],
                None,
            ],
            tyro.conf.arg(prefix_name=False),
        ]

    helptext = get_helptext_with_checks(Args)
    assert "x" in helptext
    assert "y" in helptext
    assert "none" in helptext
    assert "config:x" not in helptext
    assert "config:y" not in helptext

    assert tyro.cli(Args, args=["x"]) == Args(config=Config(name="x", value=10))
    assert tyro.cli(Args, args=["y"]) == Args(config=Config(name="y", value=20))
    assert tyro.cli(Args, args=["none"]) == Args(config=None)


def test_prefix_name_false_alongside_prefixed() -> None:
    """One field with prefix_name=False, another with default prefix_name=True."""

    AnnotatedInferenceConfig = Annotated[
        Config,
        tyro.conf.arg(
            constructor=tyro.extras.subcommand_type_from_defaults(
                {
                    "a": Config(name="a", value=1),
                    "b": Config(name="b", value=2),
                }
            )
        ),
    ]

    Args = dataclasses.make_dataclass(
        "Args",
        [
            (
                "main",
                Annotated[AnnotatedInferenceConfig, tyro.conf.arg(prefix_name=False)],
            ),
            ("secondary", Union[AnnotatedInferenceConfig, None]),
        ],
        frozen=True,
    )

    # Top-level help: main subcommands should be unprefixed.
    helptext = get_helptext_with_checks(Args)
    # main subcommands should NOT have "main:" prefix.
    assert "main:a" not in helptext
    assert "main:b" not in helptext

    result = tyro.cli(Args, args=["a", "secondary:b"])  # type: ignore[var-annotated]
    assert result == Args(
        main=Config(name="a", value=1), secondary=Config(name="b", value=2)
    )

    result = tyro.cli(Args, args=["b", "secondary:none"])
    assert result == Args(main=Config(name="b", value=2), secondary=None)


def test_prefix_name_false_plain_union() -> None:
    """prefix_name=False on a plain union (no subcommand_type_from_defaults)."""

    @dataclasses.dataclass(frozen=True)
    class Foo:
        x: int = 1

    @dataclasses.dataclass(frozen=True)
    class Bar:
        y: str = "hi"

    @dataclasses.dataclass(frozen=True)
    class Args:
        thing: Annotated[Union[Foo, Bar], tyro.conf.arg(prefix_name=False)]

    helptext = get_helptext_with_checks(Args)
    assert "foo" in helptext
    assert "bar" in helptext
    assert "thing:foo" not in helptext
    assert "thing:bar" not in helptext

    assert tyro.cli(Args, args=["foo"]) == Args(thing=Foo(x=1))
    assert tyro.cli(Args, args=["bar"]) == Args(thing=Bar(y="hi"))
