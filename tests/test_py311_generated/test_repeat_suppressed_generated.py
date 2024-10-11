"""Adapted from @mirceamironenco: https://github.com/brentyi/tyro/issues/170"""

from dataclasses import dataclass

import tyro


class LayerAExample:
    def __init__(self, **kwargs): ...


@dataclass
class LayerAConfig:
    _target: type = LayerAExample
    foo: int = 13


class LayerBExample:
    def __init__(self, **kwargs): ...


@dataclass
class LayerBConfig:
    _target: type = LayerBExample
    bar: int = 13


@dataclass
class BlockConfig:
    layer_a: LayerAConfig
    layer_b: LayerBConfig


def test_repeat_suppressed() -> None:
    assert tyro.cli(
        tyro.conf.OmitArgPrefixes[tyro.conf.SuppressFixed[BlockConfig]],
        args="--foo 14".split(" "),
    ) == BlockConfig(LayerAConfig(foo=14), LayerBConfig())
