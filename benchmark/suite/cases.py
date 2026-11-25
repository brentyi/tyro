"""Benchmark case definitions.

Each case is registered with ``@case(name)`` on a *builder*. Builders are untimed: they
construct types and arguments, then return a zero-argument callable which is what we
time. Any output and ``SystemExit`` is handled by the runner.

Cases should only use tyro's public API, so the same file can be run against different
versions of tyro.
"""

from __future__ import annotations

import contextlib
import dataclasses
import enum
import functools
import importlib.util
import pathlib
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    NamedTuple,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypeVar,
    Union,
)

from typing_extensions import Annotated, Literal, TypedDict

import tyro
import tyro.extras

Thunk = Callable[[], Any]
Builder = Callable[[], Thunk]

CASES: Dict[str, Builder] = {}


def case(name: str, requires: Tuple[str, ...] = ()) -> Callable[[Builder], Builder]:
    """Register a benchmark case. Names are formatted as `group/case`."""

    def inner(builder: Builder) -> Builder:
        assert name not in CASES, name
        if all(importlib.util.find_spec(r) is not None for r in requires):
            CASES[name] = builder
        return builder

    return inner


def _register(name: str, f: Any, args: Sequence[str], **kwargs: Any) -> None:
    CASES[name] = lambda: lambda: tyro.cli(f, args=list(args), prog="bench", **kwargs)


class Color(enum.Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


# -----------------------------------------------------------------------------
# Tiny inputs: these measure fixed overheads.
# -----------------------------------------------------------------------------


def tiny_main(name: str, count: int = 1) -> int:
    """A tiny function.

    Args:
        name: Name to greet.
        count: Number of times to greet.
    """
    return len(name) * count


@dataclasses.dataclass
class TinyConfig:
    """A tiny struct."""

    name: str
    """Name to greet."""
    count: int = 1  # Number of times to greet.


_register("tiny/function", tiny_main, ["--name", "x", "--count", "3"])
_register("tiny/dataclass", TinyConfig, ["--name", "x", "--count", "3"])
_register("tiny/primitive", int, ["5"])
_register("tiny/tuple", Tuple[int, str], ["5", "x"])
_register("tiny/help", TinyConfig, ["--help"])
_register("tiny/missing_error", TinyConfig, [])
_register("tiny/unrecognized_error", TinyConfig, ["--name", "x", "--cuont", "3"])
_register("tiny/bad_value_error", TinyConfig, ["--name", "x", "--count", "hello"])


# -----------------------------------------------------------------------------
# Flat structs.
# -----------------------------------------------------------------------------


def _make_flat(n: int, name: str, typ: Any, default: Any) -> Any:
    return dataclasses.make_dataclass(
        name,
        [
            (f"arg_{i}", typ, dataclasses.field(default_factory=lambda: default))
            for i in range(n)
        ],
    )


FlatInt100 = _make_flat(100, "FlatInt100", int, 3)
FlatInt500 = _make_flat(500, "FlatInt500", int, 3)
FlatBool100 = _make_flat(100, "FlatBool100", bool, False)
FlatOptional100 = _make_flat(100, "FlatOptional100", Optional[int], None)
FlatLiteral100 = _make_flat(100, "FlatLiteral100", Literal["a", "b", "c"], "a")
FlatEnum100 = _make_flat(100, "FlatEnum100", Color, Color.RED)
FlatTuple100 = _make_flat(100, "FlatTuple100", Tuple[int, int, int], (1, 2, 3))
FlatList100 = _make_flat(100, "FlatList100", List[int], [1, 2, 3])
FlatDict100 = _make_flat(100, "FlatDict100", Dict[str, int], {"a": 1})
FlatUnion100 = _make_flat(100, "FlatUnion100", Union[int, str, Tuple[int, int]], 1)
FlatPath100 = _make_flat(100, "FlatPath100", pathlib.Path, pathlib.Path("/tmp"))

_register("flat/int100_defaults", FlatInt100, [])
_register(
    "flat/int100_all_args",
    FlatInt100,
    [s for i in range(100) for s in (f"--arg-{i}", "1")],
)
_register("flat/int100_equals_args", FlatInt100, [f"--arg_{i}=1" for i in range(100)])
_register("flat/int100_help", FlatInt100, ["--help"])
_register("flat/int500_defaults", FlatInt500, [])
_register(
    "flat/int500_all_args",
    FlatInt500,
    [s for i in range(500) for s in (f"--arg-{i}", "1")],
)
_register("flat/int500_help", FlatInt500, ["--help"])
_register("flat/int500_unrecognized", FlatInt500, ["--arg-1234", "1"])
_register("flat/bool100", FlatBool100, [f"--arg-{i}" for i in range(100)])
_register("flat/optional100", FlatOptional100, ["--arg-3", "5"])
_register("flat/literal100", FlatLiteral100, ["--arg-3", "b"])
_register("flat/enum100", FlatEnum100, ["--arg-3", "RED"])
_register("flat/tuple100", FlatTuple100, ["--arg-3", "1", "2", "3"])
_register("flat/list100", FlatList100, ["--arg-3", "1", "2", "3"])
_register("flat/dict100", FlatDict100, ["--arg-3", "a", "1"])
_register("flat/union100", FlatUnion100, ["--arg-3", "1", "2"])
_register("flat/path100", FlatPath100, ["--arg-3", "/a"])
_register("flat/union100_help", FlatUnion100, ["--help"])


@dataclasses.dataclass(frozen=True)
class Documented:
    """A realistic struct, with realistic documentation and many types.

    Attributes:
        flow_steps: Number of flow steps.
    """

    flow_steps: int = 10
    output_mode: Literal["u", "u_but_supervise_as_eps"] = "u_but_supervise_as_eps"
    """What the network outputs."""
    timestep_embed_dim: int = 8
    """Embedding dimension for timesteps."""
    n_samples_per_action: int = 8
    """Samples per action."""
    average_losses_before_exp: bool = True
    """Average our losses before the exponential?"""
    discretize_t_for_training: bool = True  # Discretize time.
    feather_std: float = 0.0  # Standard deviation.
    # Comments above the field.
    policy_mlp_output_scale: float = 0.25
    trust_region_mode: Literal["ppo", "spo"] = "ppo"
    loss_mode: Literal["fpo", "denoising_mdp"] = "fpo"
    final_steps_only: bool = False
    sde_sigma: float = 0.0
    clipping_epsilon: float = 0.05
    batch_size: int = 1024
    """Batch size."""
    discounting: float = 0.995
    """Discount factor."""
    episode_length: int = 1000
    learning_rate: float = 3e-4
    normalize_observations: bool = True
    num_envs: int = 2048
    num_minibatches: Optional[int] = 32
    betas: Tuple[float, float] = (0.9, 0.999)
    hidden_sizes: Tuple[int, ...] = (128, 128)
    checkpoint: Optional[pathlib.Path] = None
    """Path to checkpoint."""
    color: Color = Color.RED
    tags: List[str] = dataclasses.field(default_factory=lambda: ["a", "b"])
    """Experiment tags."""


_register("documented/defaults", Documented, [])
_register(
    "documented/some_args",
    Documented,
    ["--flow-steps", "3", "--no-final-steps-only", "--betas", "0.1", "0.2"],
)
_register("documented/help", Documented, ["--help"])


# -----------------------------------------------------------------------------
# Nested structs.
# -----------------------------------------------------------------------------


@dataclasses.dataclass
class Leaf:
    """Leaf docstring."""

    a: int = 1
    """Field a."""
    b: float = 2.0
    """Field b."""
    c: Optional[str] = None
    """Field c."""


@dataclasses.dataclass
class Wide:
    """Many children of the same type."""

    x0: Leaf = dataclasses.field(default_factory=Leaf)
    x1: Leaf = dataclasses.field(default_factory=Leaf)
    x2: Leaf = dataclasses.field(default_factory=Leaf)
    x3: Leaf = dataclasses.field(default_factory=Leaf)
    x4: Leaf = dataclasses.field(default_factory=Leaf)
    x5: Leaf = dataclasses.field(default_factory=Leaf)
    x6: Leaf = dataclasses.field(default_factory=Leaf)
    x7: Leaf = dataclasses.field(default_factory=Leaf)


def _make_deep(depth: int) -> Any:
    cls: Any = Leaf
    for i in range(depth):
        cls = dataclasses.make_dataclass(
            f"Deep{i}",
            [
                ("v", int, dataclasses.field(default=i)),
                ("inner", cls, dataclasses.field(default_factory=cls)),
            ],
        )
    return cls


Deep10 = _make_deep(10)
Deep40 = _make_deep(40)


def _make_tree(depth: int, branching: int) -> Any:
    cls: Any = Leaf
    for i in range(depth):
        cls = dataclasses.make_dataclass(
            f"Tree{i}",
            [
                (f"b{j}", cls, dataclasses.field(default_factory=cls))
                for j in range(branching)
            ],
        )
    return cls


Tree3x4 = _make_tree(3, 4)

_register("nested/wide_defaults", Wide, ["--x3.a", "3"])
_register("nested/wide_help", Wide, ["--help"])
_register("nested/wide_instance_default", Wide, ["--x3.a", "3"], default=Wide())
_register("nested/deep10", Deep10, ["--v", "3"])
_register("nested/deep40", Deep40, ["--v", "3"])
_register("nested/deep40_help", Deep40, ["--help"])
_register("nested/tree64_leaves", Tree3x4, ["--b0.b1.b2.a", "3"])
_register("nested/tree64_leaves_help", Tree3x4, ["--help"])
_register(
    "nested/markers",
    Wide,
    ["--x3.a", "3"],
    config=(
        tyro.conf.FlagConversionOff,
        tyro.conf.UseAppendAction,
        tyro.conf.HelptextFromCommentsOff,
    ),
)


# -----------------------------------------------------------------------------
# Other kinds of structs.
# -----------------------------------------------------------------------------

T = TypeVar("T")
S = TypeVar("S")


@dataclasses.dataclass
class GenericLeaf(Generic[T]):
    x: T
    y: List[T]


@dataclasses.dataclass
class GenericPair(Generic[T, S]):
    a: GenericLeaf[T]
    b: GenericLeaf[S]
    c: Tuple[T, S]


@dataclasses.dataclass
class GenericChild(GenericPair[int, T], Generic[T]):
    d: Optional[T] = None


class TD(TypedDict, total=False):
    """A typed dictionary."""

    x: int
    y: str
    z: Tuple[int, int]


class NT(NamedTuple):
    """A named tuple."""

    x: int
    y: str = "hello"
    z: Tuple[int, int] = (1, 2)


class PlainClass:
    """Plain class.

    Args:
        a: The a value.
        b: The b value.
    """

    def __init__(self, a: int, b: str = "3", *, c: Tuple[int, ...] = (1, 2)) -> None:
        self.a = a


def many_arg_function(
    a: int,
    b: int = 3,
    c: float = 3.0,
    d: Optional[str] = None,
    e: Literal[1, 2, 3] = 1,
    f: Color = Color.RED,
    g: Tuple[int, int] = (3, 3),
    h: bool = False,
    inner: Leaf = Leaf(),
) -> None:
    """A function.

    Args:
        a: Argument a.
        b: Argument b.
        c: Argument c.
        d: Argument d.
        e: Argument e.
        f: Argument f.
        g: Argument g.
        h: Argument h.
        inner: Nested struct.
    """


def varargs_function(*args: int, **kwargs: float) -> None:
    """Variadic function."""


_register(
    "structs/generic",
    GenericPair[int, str],
    "--a.x 1 --a.y 1 2 --b.x a --b.y b c --c 3 a".split(),
)
_register(
    "structs/generic_inherited",
    GenericChild[str],
    "--a.x 1 --a.y 1 2 --b.x a --b.y b c --c 3 a".split(),
)
_register("structs/typeddict", TD, ["--x", "3"])
_register("structs/namedtuple", NT, ["--x", "3"])
_register("structs/class", PlainClass, ["--a", "3"])
_register("structs/function", many_arg_function, ["--a", "3"])
_register("structs/function_help", many_arg_function, ["--help"])
_register("structs/varargs", varargs_function, "--args 1 2 3 --kwargs a 1 b 2".split())
_register("structs/partial", functools.partial(many_arg_function, b=5), ["--a", "3"])
_register(
    "structs/dict_default",
    dict,
    ["--a", "3", "--b.c", "5"],
    default={"a": 1, "b": {"c": 3, "d": "x", "e": (1, 2)}, "f": 1.0},
)
_register(
    "structs/list_of_structs",
    List[Leaf],
    ["--3.a", "5"],
    default=[Leaf() for _ in range(10)],
)
_register("structs/namedtuple_help", NT, ["--help"])


@case("structs/pydantic", requires=("pydantic",))
def _pydantic() -> Thunk:
    import pydantic

    create_model: Any = pydantic.create_model
    inner = create_model("Inner", **{f"i{i}": (int, i) for i in range(10)})
    model = create_model(
        "Model",
        inner=(inner, inner()),
        **{f"x{i}": (Optional[int], None) for i in range(20)},
    )
    return lambda: tyro.cli(model, args=["--x3", "1", "--inner.i3", "5"], prog="bench")


@case("structs/attrs", requires=("attr",))
def _attrs() -> Thunk:
    import attr

    cls = attr.make_class(
        "AttrsModel", {f"x{i}": attr.ib(type=int, default=3) for i in range(30)}
    )
    return lambda: tyro.cli(cls, args=["--x3", "1"], prog="bench")


@case("structs/msgspec", requires=("msgspec",))
def _msgspec() -> Thunk:
    import msgspec

    cls = msgspec.defstruct("MsgspecModel", [(f"x{i}", int, 3) for i in range(30)])
    return lambda: tyro.cli(cls, args=["--x3", "1"], prog="bench")


# -----------------------------------------------------------------------------
# Subcommands.
# -----------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class AlgorithmConfig:
    """Algorithm configuration.

    Longer description of the algorithm."""

    flow_steps: int = 1
    """Number of flow steps."""
    learning_rate: float = 3e-4
    """Learning rate."""
    mode: Literal["a", "b"] = "a"
    """Mode."""


def _subcommand_type(n: int) -> Any:
    return tyro.extras.subcommand_type_from_defaults(
        {f"algo-{i}": AlgorithmConfig(flow_steps=i) for i in range(n)},
        descriptions={f"algo-{i}": f"Algorithm number {i}." for i in range(n)},
    )


def _experiment_type(n: int) -> Any:
    @dataclasses.dataclass
    class ExperimentConfig:
        algorithm: Annotated[
            AlgorithmConfig, tyro.conf.arg(constructor=_subcommand_type(n))
        ]
        seed: int = 0

    # Resolve local annotations.
    ExperimentConfig.__annotations__["algorithm"] = Annotated[
        AlgorithmConfig, tyro.conf.arg(constructor=_subcommand_type(n))
    ]
    ExperimentConfig.__annotations__["seed"] = int
    return ExperimentConfig


Experiment100 = _experiment_type(100)
Experiment500 = _experiment_type(500)
Experiment100Default = dataclasses.make_dataclass(
    "Experiment100Default",
    [
        (
            "algorithm",
            _subcommand_type(100),
            dataclasses.field(default=AlgorithmConfig(flow_steps=50)),
        )
    ],
)
# The default won't match any of the subcommand defaults by value.
Experiment100DefaultUnmatched = dataclasses.make_dataclass(
    "Experiment100DefaultUnmatched",
    [
        (
            "algorithm",
            _subcommand_type(100),
            dataclasses.field(default=AlgorithmConfig(flow_steps=5000)),
        )
    ],
)

UniqueStructs50 = [
    dataclasses.make_dataclass(
        f"Unique{i}",
        [(f"field_{j}", int, dataclasses.field(default=j)) for j in range(20)],
        namespace={"__doc__": f"Unique struct {i}."},
    )
    for i in range(50)
]
UniqueUnion50 = Union[tuple(UniqueStructs50)]  # type: ignore
UniqueExperiment50 = dataclasses.make_dataclass(
    "UniqueExperiment50",
    [
        (
            "inner",
            UniqueUnion50,
            dataclasses.field(default_factory=UniqueStructs50[25]),
        )
    ],
)

_register("subcommands/defaults100", Experiment100, ["algorithm:algo-50"])
_register("subcommands/defaults100_help", Experiment100, ["--help"])
_register(
    "subcommands/defaults100_sub_help", Experiment100, ["algorithm:algo-5", "--help"]
)
_register("subcommands/defaults500", Experiment500, ["algorithm:algo-50"])
_register("subcommands/defaults100_default", Experiment100Default, [])
_register(
    "subcommands/defaults100_default_unmatched", Experiment100DefaultUnmatched, []
)
_register(
    "subcommands/defaults100_unrecognized", Experiment100, ["algorithm:algo-5", "--x"]
)
_register("subcommands/unique50", UniqueUnion50, ["unique25", "--field-3", "5"])
_register("subcommands/unique50_help", UniqueUnion50, ["--help"])
_register("subcommands/unique50_missing", UniqueUnion50, [])
_register("subcommands/unique50_default", UniqueExperiment50, [])
_register(
    "subcommands/unique50_default_selected",
    UniqueExperiment50,
    ["inner:unique3", "--inner.field-3", "3"],
)


def _sequenced(n_groups: int, n_options: int) -> Any:
    return dataclasses.make_dataclass(
        "Sequenced",
        [
            (
                f"group{i}",
                _subcommand_type(n_options),
                dataclasses.field(default=AlgorithmConfig(flow_steps=0)),
            )
            for i in range(n_groups)
        ],
    )


Sequenced5x10 = _sequenced(5, 10)
Sequenced5x10Args = [s for i in range(5) for s in (f"group{i}:algo-{i}",)]
_register("subcommands/sequenced_5x10", Sequenced5x10, Sequenced5x10Args)
_register("subcommands/sequenced_5x10_defaults", Sequenced5x10, [])
_register("subcommands/sequenced_5x10_help", Sequenced5x10, ["--help"])
_register(
    "subcommands/sequenced_5x10_cascade",
    Sequenced5x10,
    ["--group3.learning-rate", "0.1"],
    config=(tyro.conf.CascadeSubcommandArgs,),
)
_register(
    "subcommands/sequenced_5x10_cascade_help",
    Sequenced5x10,
    ["--help"],
    config=(tyro.conf.CascadeSubcommandArgs,),
)
_register(
    "subcommands/sequenced_5x10_avoid",
    Sequenced5x10,
    ["--group3.learning-rate", "0.1"],
    config=(tyro.conf.AvoidSubcommands,),
)


def _nested_subcommands(depth: int, n: int) -> Any:
    options: Any = _subcommand_type(n)
    for i in range(depth):
        structs = [
            dataclasses.make_dataclass(
                f"Level{i}Option{j}",
                [("inner", options), ("x", int, dataclasses.field(default=3))],
            )
            for j in range(n)
        ]
        options = Union[tuple(structs)]  # type: ignore
    return options


_register(
    "subcommands/nested_3x5",
    _nested_subcommands(3, 5),
    "level2-option3 inner:level1-option2 inner.inner:level0-option1 "
    "inner.inner.inner:algo-3".split(),
)

_functions = {
    f"command-{i}": functools.partial(many_arg_function, b=i) for i in range(30)
}


@case("subcommands/cli_from_dict")
def _cli_from_dict() -> Thunk:
    return lambda: tyro.extras.subcommand_cli_from_dict(
        _functions, args=["command-5", "--a", "3"], prog="bench"
    )


@case("subcommands/cli_from_dict_help")
def _cli_from_dict_help() -> Thunk:
    return lambda: tyro.extras.subcommand_cli_from_dict(
        _functions, args=["--help"], prog="bench"
    )


@case("subcommands/app")
def _app() -> Thunk:
    app: Any = tyro.extras.SubcommandApp()
    for i in range(30):
        app.command(many_arg_function, name=f"command{i}")
    return lambda: app.cli(args=["command5", "--a", "3"], prog="bench")


@case("subcommands/overridable_config")
def _overridable() -> Thunk:
    configs = {f"c{i}": (f"Config {i}.", Documented(flow_steps=i)) for i in range(30)}
    return lambda: tyro.extras.overridable_config_cli(
        configs, args=["c5", "--batch-size", "3"], prog="bench"
    )


# -----------------------------------------------------------------------------
# Variable-length parsing + backtracking.
# -----------------------------------------------------------------------------


@dataclasses.dataclass
class SeqInt:
    x: List[int]


@dataclasses.dataclass
class SeqPair:
    x: List[Tuple[int, int]]


@dataclasses.dataclass
class SeqUnion:
    x: List[Union[int, Tuple[int, int, int]]]


@dataclasses.dataclass
class SeqUnionMixed:
    x: Tuple[Union[Tuple[int, str], Tuple[int, int, int], bool], ...]


@dataclasses.dataclass
class SeqNested:
    x: List[List[int]]


@dataclasses.dataclass
class SeqDict:
    x: Dict[str, int]


@dataclasses.dataclass
class SeqDictVariable:
    x: Dict[str, Union[int, Tuple[int, int]]]


@dataclasses.dataclass
class SeqDictList:
    x: Dict[str, List[int]]


@dataclasses.dataclass
class SeqTuples:
    x: Tuple[List[int], List[str], List[int]]


@dataclasses.dataclass
class SeqLiteral:
    x: List[Literal["a", "b", "c"]]


@dataclasses.dataclass
class SeqSet:
    x: Set[str]


@dataclasses.dataclass
class SeqAppend:
    x: tyro.conf.UseAppendAction[List[int]]


_NUMS = [str(i % 10) for i in range(10_000)]
_register("sequences/list_int_10k", SeqInt, ["--x"] + _NUMS)
_register("sequences/list_int_10k_bad_last", SeqInt, ["--x"] + _NUMS + ["bad"])
_register("sequences/set_str_10k", SeqSet, ["--x"] + _NUMS)
_register("sequences/list_literal_10k", SeqLiteral, ["--x"] + ["a", "b"] * 5000)
_register("sequences/list_pair_10k", SeqPair, ["--x"] + _NUMS)
_register("sequences/list_pair_odd_fail", SeqPair, ["--x"] + _NUMS[:999])
_register("sequences/list_union_1k", SeqUnion, ["--x"] + _NUMS[:1000])
_register("sequences/list_union_16_fail", SeqUnion, ["--x"] + _NUMS[:16] + ["bad"])
_register("sequences/list_union_22_fail", SeqUnion, ["--x"] + _NUMS[:22] + ["bad"])
_register(
    "sequences/tuple_union_mixed_30",
    SeqUnionMixed,
    ["--x"] + ["1", "a", "1", "2", "3", "True"] * 5,
)
_register("sequences/nested_list_300", SeqNested, ["--x"] + _NUMS[:300])
_register("sequences/dict_2k", SeqDict, ["--x"] + [f"{i}" for i in range(4000)])
_register(
    "sequences/dict_variable_100",
    SeqDictVariable,
    ["--x"] + [s for i in range(50) for s in (f"k{i}", "1", "2")],
)
_register(
    "sequences/dict_list",
    SeqDictList,
    ["--x"] + [s for i in range(5) for s in (f"k{i}", "1", "2")],
)
_register(
    "sequences/append_500",
    SeqAppend,
    [s for i in range(500) for s in ("--x", str(i))],
)


def _positional_list(x: Tuple[int, ...], y: int, /) -> None: ...


_register("sequences/positional_5k", _positional_list, _NUMS[:5000])


# -----------------------------------------------------------------------------
# Shell completion.
# -----------------------------------------------------------------------------


def _completion(shell: str) -> Thunk:
    return lambda: tyro.cli(
        Sequenced5x10,
        args=["--tyro-print-completion", shell],
        prog="bench",
    )


CASES["completion/bash"] = lambda: _completion("bash")
CASES["completion/zsh"] = lambda: _completion("zsh")
CASES["completion/fish"] = lambda: _completion("fish")


# -----------------------------------------------------------------------------
# Argparse backend.
# -----------------------------------------------------------------------------


@contextlib.contextmanager
def _argparse_backend() -> Any:
    old = tyro._experimental_options["backend"]
    tyro._experimental_options["backend"] = "argparse"
    try:
        yield
    finally:
        tyro._experimental_options["backend"] = old


def _with_argparse(builder: Builder) -> Builder:
    def wrapped() -> Thunk:
        thunk = builder()

        def inner() -> Any:
            with _argparse_backend():
                return thunk()

        return inner

    return wrapped


for _name in (
    "tiny/dataclass",
    "tiny/help",
    "flat/int100_all_args",
    "flat/int100_help",
    "nested/wide_defaults",
    "subcommands/defaults100",
    "subcommands/sequenced_5x10_avoid",
):
    CASES["argparse/" + _name.replace("/", "_")] = _with_argparse(CASES[_name])


assert all(isinstance(k, str) and "/" in k for k in CASES)
