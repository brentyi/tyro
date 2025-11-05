import dataclasses
from typing import TYPE_CHECKING, Optional, Union

from typing_extensions import Annotated

import tyro


@dataclasses.dataclass
class A:
    x: int


def test_union_from_mapping():
    base_configs = {
        "one": A(1),
        "two": A(2),
        "three": A(3),
    }
    ConfigUnion = tyro.extras.subcommand_type_from_defaults(base_configs)

    assert tyro.cli(ConfigUnion, args="one".split(" ")) == A(1)
    assert tyro.cli(ConfigUnion, args="two".split(" ")) == A(2)
    assert tyro.cli(ConfigUnion, args="two --x 4".split(" ")) == A(4)
    assert tyro.cli(ConfigUnion, args="three".split(" ")) == A(3)


def test_union_from_mapping_in_function():
    base_configs = {
        "one": A(1),
        "two": A(2),
        "three": A(3),
    }

    if TYPE_CHECKING:
        ConfigUnion = A
    else:
        ConfigUnion = tyro.extras.subcommand_type_from_defaults(base_configs)

    def main(config: ConfigUnion, flag: bool = False) -> Optional[A]:  # type: ignore
        if flag:
            return config
        return None

    assert tyro.cli(main, args="--flag config:one".split(" ")) == A(1)
    assert tyro.cli(main, args="--flag config:one --config.x 3".split(" ")) == A(3)
    assert tyro.cli(main, args="config:one --config.x 1".split(" ")) is None

    assert tyro.cli(main, args="--flag config:two".split(" ")) == A(2)
    assert tyro.cli(main, args="--flag config:two --config.x 3".split(" ")) == A(3)
    assert tyro.cli(main, args="config:two --config.x 1".split(" ")) is None


def test_union_from_mapping_with_none_default():
    """Test that default matching works correctly when None is one of the options.

    This is a regression test for a bug where the subcommand matcher would incorrectly
    match any value against None when None was the first option in the union.
    """

    @dataclasses.dataclass
    class Config:
        x: Annotated[
            Union[A, None],
            tyro.conf.arg(
                constructor=tyro.extras.subcommand_type_from_defaults(
                    {"none": None, "A": A(3)}
                )
            ),
        ] = None

    # When default=Config(x=A(5)), the default subcommand should be "x:A", not "x:none".
    result = tyro.cli(Config, default=Config(x=A(5)), args=[])
    assert result.x is not None, "Default should be A(5), not None"
    assert result.x.x == 5, f"Expected x=5, got x={result.x.x}"

    # Test that we can still explicitly select the none subcommand.
    result = tyro.cli(Config, default=Config(x=A(5)), args=["x:none"])
    assert result.x is None, "Should be None when x:none is selected"

    # Test that we can override the default value.
    result = tyro.cli(Config, default=Config(x=A(5)), args=["x:A", "--x.x", "10"])
    assert result.x is not None
    assert result.x.x == 10
