import dataclasses
from typing import Any, Literal, Optional, Type, Union

import pytest
import tyro

from helptext_utils import get_helptext_with_checks


def test_list() -> None:
    def main(x: list[bool]) -> Any:
        return x

    assert tyro.cli(main, args=["--x", "True", "False"]) == [True, False]


def test_tuple() -> None:
    def main(x: tuple[bool, str]) -> Any:
        return x

    assert tyro.cli(main, args=["--x", "True", "False"]) == (True, "False")


def test_tuple_nested() -> None:
    @dataclasses.dataclass
    class Args:
        a: int

    def main(x: tuple[Args, Args]) -> Any:
        return x

    assert tyro.cli(main, args=["--x.0.a", "3", "--x.1.a", "4"]) == (Args(3), Args(4))


def test_tuple_variable() -> None:
    def main(x: tuple[Union[bool, str], ...]) -> Any:
        return x

    assert tyro.cli(main, args=["--x", "True", "Wrong"]) == (True, "Wrong")


def test_super_nested() -> None:
    def main(
        x: Optional[
            list[
                tuple[
                    Optional[int],
                    Literal[3, 4],
                    Union[tuple[int, int], tuple[str, str]],
                ]
            ]
        ] = None,
    ) -> Any:
        return x

    assert tyro.cli(main, args=[]) is None
    assert tyro.cli(main, args="--x None".split(" ")) is None
    assert tyro.cli(main, args="--x None 3 2 2".split(" ")) == [(None, 3, (2, 2))]
    assert tyro.cli(main, args="--x 2 3 x 2".split(" ")) == [(2, 3, ("x", "2"))]
    assert tyro.cli(main, args="--x 2 3 x 2 2 3 1 2".split(" ")) == [
        (2, 3, ("x", "2")),
        (2, 3, (1, 2)),
    ]
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--help"])


def test_tuple_direct() -> None:
    assert tyro.cli(tuple[int, ...], args="1 2".split(" ")) == (1, 2)  # type: ignore
    assert tyro.cli(tuple[int, int], args="1 2".split(" ")) == (1, 2)  # type: ignore


try:
    from torch.optim.lr_scheduler import LinearLR, LRScheduler

    def test_type_with_init_false() -> None:
        """https://github.com/brentyi/tyro/issues/235"""

        @dataclasses.dataclass(frozen=True)
        class LinearLRConfig:
            _target: type[LRScheduler] = dataclasses.field(
                init=False, default_factory=lambda: LinearLR
            )
            _target2: Type[LRScheduler] = dataclasses.field(
                init=False, default_factory=lambda: LinearLR
            )
            start_factor: float = 1.0 / 3
            end_factor: float = 1.0
            total_iters: Optional[int] = None

        def main(config: LinearLRConfig) -> LinearLRConfig:
            return config

        assert tyro.cli(main, args=[]) == LinearLRConfig()
        assert "_target" not in get_helptext_with_checks(LinearLRConfig)
except ImportError:
    # We can't install PyTorch in Python 3.13.
    import sys

    assert sys.version_info >= (3, 13)
