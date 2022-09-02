from __future__ import annotations

import dataclasses
import functools
import inspect
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    List,
    Protocol,
    Tuple,
    Type,
    TypeVar,
    cast,
    get_args,
)

import omegaconf
import yaml
from typing_extensions import ParamSpec, get_type_hints, reveal_type

from .. import _cli, _fields

P = ParamSpec("P")
T_co = TypeVar("T_co", covariant=True)


class Args(Protocol[T_co]):
    """Protocol type for creating configuration structures from the arguments of a
    type's constructor.

    Should not be directly instantiated; see `make_args()`."""

    def instantiate(self) -> T_co:
        ...

    def __class_getitem__(cls, contained_type: Type):
        class Dummy:
            __name__ = contained_type.__name__
            __dcargs_mock_type__ = contained_type

            def __call__(self, *args, **kwargs):
                return _ArgsImp(contained_type, *args, **kwargs)

        return Dummy()

    @staticmethod
    def of(target: Callable[P, T_co]) -> Callable[P, Args[T_co]]:
        """Helper for creating argument structures.

        Example usage:
            args = make_args(SomePythonClass)(arguments)
            instance = args.instantiate()

        """
        return functools.partial(_ArgsImp, target)  # type: ignore


class _ArgsImp(Args):
    def __init__(self, target: Type, *args: Tuple[Any, ...], **kwargs: Dict[str, Any]):
        self.target = target
        if len(args) > 0:
            self.__positional_args__ = args
        for k, v in kwargs.items():
            setattr(self, k, v)

    def instantiate(self):
        args = getattr(self, "__positional_args__", ())
        kwargs = vars(self)
        return self.target(*args, **kwargs)  # type: ignore

    def __repr__(self):
        return f"Arguments[{self.target.__name__}]" + str(vars(self))

    def __dcargs_mock_type__(self):
        print(self.target)
        return self.target


dcargs = _cli


class NeuralNetwork:
    def __init__(self, num_layers: int, units: int):
        ...


@dataclasses.dataclass
class Config:
    network_no_defaults: Args[NeuralNetwork]
    network_with_defaults: Args[NeuralNetwork] = Args.of(NeuralNetwork)(
        # Should type-check correctly.
        num_layers=30,
        units=5,
    )


cfg = dcargs.cli(Config)
reveal_type(cfg)
network = cfg.network_no_defaults.instantiate()
reveal_type(network)
