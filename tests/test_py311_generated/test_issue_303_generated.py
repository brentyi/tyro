from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Annotated, Generic, TypeVar

from helptext_utils import get_helptext_with_checks

import tyro


class Generator(ABC): ...


class VLLMGenerator(Generator): ...


OutT = TypeVar("OutT")


class BuilderConfig(Generic[OutT]): ...


@dataclass
class GeneratorConfig(BuilderConfig[Generator]): ...


@dataclass
class VLLMSamplingConfig:
    n: int = 1

    temperature: float = 1.0


@dataclass
class VLLMGeneratorConfig(GeneratorConfig):
    _target: type[Generator] = field(init=False, default_factory=lambda: VLLMGenerator)

    sample: VLLMSamplingConfig = field(default_factory=lambda: VLLMSamplingConfig())


@dataclass
class TorchProfilerConfig:
    skip_n_steps: int = 4

    wait_n_steps: int = 0

    num_warmup_steps: int = 1

    num_active_steps: int = 4

    repeat: int = 1


CLITorchProfilerConfig = Annotated[TorchProfilerConfig, tyro.conf.subcommand(name="on")]


@dataclass
class EvalConfig:
    generator: VLLMGeneratorConfig = field(
        default_factory=lambda: VLLMGeneratorConfig()
    )

    profiler: CLITorchProfilerConfig | None = None


def test_issue_303() -> None:
    assert "(default: profiler:None)" in get_helptext_with_checks(
        EvalConfig, use_underscores=True, config=(tyro.conf.ConsolidateSubcommandArgs,)
    )
    assert isinstance(
        tyro.cli(
            EvalConfig,
            use_underscores=False,
            args=[],
        ),
        EvalConfig,
    )
    assert isinstance(
        tyro.cli(
            EvalConfig,
            use_underscores=True,
            args=[],
        ),
        EvalConfig,
    )
    assert isinstance(
        tyro.cli(
            EvalConfig,
            use_underscores=False,
            config=(tyro.conf.ConsolidateSubcommandArgs,),
            args=[],
        ),
        EvalConfig,
    )
    assert isinstance(
        tyro.cli(
            EvalConfig,
            use_underscores=True,
            config=(tyro.conf.ConsolidateSubcommandArgs,),
            args=[],
        ),
        EvalConfig,
    )
