from dataclasses import dataclass
from typing import Any, Callable, Tuple

import torch
from helptext_utils import get_helptext_with_checks
from torch import nn

import tyro


def test_torch_device() -> None:
    def main(device: torch.device) -> torch.device:
        return device

    assert tyro.cli(main, args=["--device", "cpu"]) == torch.device("cpu")


def test_supports_inference_mode_decorator() -> None:
    @torch.inference_mode()
    def main(x: int, device: str) -> Tuple[int, str]:
        return x, device

    assert tyro.cli(main, args="--x 3 --device cuda".split(" ")) == (3, "cuda")


def test_torch_device_2() -> None:
    assert tyro.cli(torch.device, args=["cpu"]) == torch.device("cpu")


def test_unparsable() -> None:
    @dataclass
    class Struct:
        a: int = 5
        b: str = "7"

    def main(x: Any = Struct()):
        pass

    helptext = get_helptext_with_checks(main)
    assert "--x {fixed}" not in helptext

    def main2(x: Callable = nn.ReLU):
        pass

    helptext = get_helptext_with_checks(main2)
    assert "--x {fixed}" in helptext
    assert "(fixed to:" in helptext
    assert "torch" in helptext
