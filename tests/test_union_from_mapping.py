import dataclasses
from typing import TYPE_CHECKING, Optional

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
