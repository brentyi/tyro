import dataclasses
from typing import Optional

import dcargs


@dataclasses.dataclass
class A:
    x: int


def test_union_from_mapping():
    base_configs = {
        "one": A(1),
        "two": A(2),
        "three": A(3),
    }
    ConfigUnion = dcargs.extras.union_type_from_mapping(base_configs)

    assert dcargs.cli(ConfigUnion, args="one".split(" ")) == A(1)
    assert dcargs.cli(ConfigUnion, args="two".split(" ")) == A(2)
    assert dcargs.cli(ConfigUnion, args="two --x 4".split(" ")) == A(4)
    assert dcargs.cli(ConfigUnion, args="three".split(" ")) == A(3)


def test_union_from_mapping_in_function():
    base_configs = {
        "one": A(1),
        "two": A(2),
        "three": A(3),
    }

    # Hack for mypy. Not needed for pyright.
    ConfigUnion = A
    ConfigUnion = dcargs.extras.union_type_from_mapping(base_configs)  # type: ignore

    def main(config: ConfigUnion, flag: bool = False) -> Optional[A]:
        if flag:
            return config
        return None

    assert dcargs.cli(main, args="--flag config:one".split(" ")) == A(1)
    assert dcargs.cli(main, args="--flag config:one --config.x 3".split(" ")) == A(3)
    assert dcargs.cli(main, args="config:one --config.x 1".split(" ")) is None

    assert dcargs.cli(main, args="--flag config:two".split(" ")) == A(2)
    assert dcargs.cli(main, args="--flag config:two --config.x 3".split(" ")) == A(3)
    assert dcargs.cli(main, args="config:two --config.x 1".split(" ")) is None
