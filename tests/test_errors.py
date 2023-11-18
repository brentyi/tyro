import contextlib
import dataclasses
import io
from typing import List, Tuple, TypeVar, Union

import pytest

import tyro


def test_ambiguous_collection_0() -> None:
    @dataclasses.dataclass
    class A:
        x: Tuple[Tuple[int, ...], ...]

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(A, args=["--x", "0", "1"])


def test_ambiguous_collection_1() -> None:
    @dataclasses.dataclass
    class A:
        x: List[List[int]]

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(A, args=["--x", "0", "1"])


def test_ambiguous_collection_2() -> None:
    def main(x: Tuple[List[str], List[str]]) -> None:
        pass

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--help"])


def test_ambiguous_collection_3() -> None:
    def main(x: List[Union[Tuple[int, int], Tuple[int, int, int]]]) -> None:
        pass

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--help"])


# Must be global.
@dataclasses.dataclass
class _CycleDataclass:
    x: "_CycleDataclass"


def test_cycle() -> None:
    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(_CycleDataclass, args=[])


def test_uncallable_annotation() -> None:
    def main(arg: 5) -> None:  # type: ignore
        pass

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=[])


def test_nested_annotation() -> None:
    @dataclasses.dataclass
    class OneIntArg:
        x: int

    def main(arg: List[OneIntArg]) -> List[OneIntArg]:  # type: ignore
        return arg

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=[])

    @dataclasses.dataclass
    class OneStringArg:
        x: str

    def main(arg: List[OneStringArg]) -> List[OneStringArg]:  # type: ignore
        return arg

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--arg", "0", "1", "2"])

    @dataclasses.dataclass
    class TwoStringArg:
        x: str
        y: str

    def main2(arg: List[TwoStringArg]) -> None:
        pass

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main2, args=[])


def test_missing_annotation_1() -> None:
    def main(a, b) -> None:
        pass

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--help"])


def test_missing_annotation_2() -> None:
    def main(*, a) -> None:
        pass

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--help"])


def test_tuple_needs_default() -> None:
    def main(arg: tuple) -> None:  # type: ignore
        pass

    # This formerly raised an error, but now defaults to Tuple[str, ...].
    #  with pytest.raises(tyro.UnsupportedTypeAnnotationError):
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--help"])


def test_unbound_typevar() -> None:
    T = TypeVar("T")

    def main(arg: T) -> None:  # type: ignore
        pass

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--help"])


def test_missing_default_fixed() -> None:
    def main(value: tyro.conf.SuppressFixed[tyro.conf.Fixed[int]]) -> int:
        return value

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--help"])


def test_missing_default_suppressed() -> None:
    def main(value: tyro.conf.Suppress[int]) -> int:
        return value

    with pytest.raises(tyro.UnsupportedTypeAnnotationError):
        tyro.cli(main, args=["--help"])


def test_ambiguous_sequence() -> None:
    def main(value: list) -> None:
        return None

    # This formerly raised an error, but now defaults to List[str].
    #  with pytest.raises(tyro.UnsupportedTypeAnnotationError):
    with pytest.raises(SystemExit):
        tyro.cli(main, args=["--help"])


def test_similar_arguments_basic() -> None:
    @dataclasses.dataclass
    class RewardConfig:
        track: bool

    @dataclasses.dataclass
    class Class:
        reward: RewardConfig

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(Class, args="--reward.trac".split(" "))

    error = target.getvalue()
    assert "Unrecognized argument" in error
    assert "Perhaps you meant:" in error

    # --reward.track should appear in both the usage string and as a similar argument.
    assert error.count("--reward.track") == 1
    assert error.count("--help") == 1


def test_similar_arguments_subcommands() -> None:
    @dataclasses.dataclass
    class RewardConfig:
        track: bool

    @dataclasses.dataclass
    class ClassA:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassB:
        reward: RewardConfig

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(Union[ClassA, ClassB], args="--reward.trac".split(" "))  # type: ignore

    error = target.getvalue()
    assert "Unrecognized argument" in error
    assert "Perhaps you meant:" in error
    assert error.count("--reward.track") == 1
    assert error.count("--help") == 3


def test_similar_arguments_subcommands_multiple() -> None:
    @dataclasses.dataclass
    class RewardConfig:
        track: bool
        trace: int

    @dataclasses.dataclass
    class ClassA:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassB:
        reward: RewardConfig

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(Union[ClassA, ClassB], args="--fjdkslaj --reward.trac".split(" "))  # type: ignore

    error = target.getvalue()
    assert "Unrecognized argument" in error
    assert "Arguments similar to --reward.trac" in error
    assert error.count("--reward.track {True,False}") == 1
    assert error.count("--reward.trace INT") == 1
    assert error.count("--help") == 5


def test_similar_arguments_subcommands_multiple_contains_match() -> None:
    @dataclasses.dataclass
    class RewardConfig:
        track: bool
        trace: int

    @dataclasses.dataclass
    class ClassA:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassB:
        reward: RewardConfig

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(Union[ClassA, ClassB], args="--rd.trac".split(" "))  # type: ignore

    error = target.getvalue()
    assert "Unrecognized argument" in error
    assert "Perhaps you meant:" in error
    assert error.count("--reward.track {True,False}") == 1
    assert error.count("--reward.trace INT") == 1
    assert error.count("--help") == 5  # 2 subcommands * 2 arguments + usage hint.


def test_similar_arguments_subcommands_multiple_contains_match_alt() -> None:
    @dataclasses.dataclass
    class RewardConfig:
        track: bool
        trace: int

    @dataclasses.dataclass
    class ClassA:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassB:
        reward: RewardConfig

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(Union[ClassA, ClassB], args="--track".split(" "))  # type: ignore

    error = target.getvalue()
    assert "Unrecognized argument" in error
    assert "Perhaps you meant:" in error
    assert error.count("--reward.track {True,False}") == 1
    assert (
        error.count("--help") == 3
    )  # Should show two possible subcommands + usage hint.


def test_similar_arguments_subcommands_overflow_different() -> None:
    @dataclasses.dataclass
    class RewardConfig:
        track0: bool
        track1: bool
        track2: bool
        track3: bool
        track4: bool
        track5: bool
        track6: bool
        track7: bool
        track8: bool
        track9: bool
        track10: bool
        track11: bool
        track12: bool
        track13: bool
        track14: bool
        track15: bool
        track16: bool

    @dataclasses.dataclass
    class ClassA:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassB:
        reward: RewardConfig

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(Union[ClassA, ClassB], args="--track".split(" "))  # type: ignore

    error = target.getvalue()
    assert "Unrecognized argument" in error
    assert "Perhaps you meant:" in error
    assert error.count("--reward.track") == 10
    assert "[...]" not in error
    assert error.count("--help") == 21

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        # --tracked is intentionally between 0.8 ~ 0.9 similarity to track{i} for test
        # coverage.
        tyro.cli(RewardConfig, args="--tracked".split(" "))  # type: ignore

    # Usage print should be clipped.
    error = target.getvalue()
    assert "For full helptext, run" in error


def test_similar_arguments_subcommands_overflow_same() -> None:
    @dataclasses.dataclass
    class RewardConfig:
        track: bool

    @dataclasses.dataclass
    class ClassA:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassB:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassC:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassD:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassE:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassF:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassG:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassH:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassI:
        reward: RewardConfig

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(  # type: ignore
            Union[
                ClassA, ClassB, ClassC, ClassD, ClassE, ClassF, ClassG, ClassH, ClassI
            ],
            args="--track".split(" "),
        )

    error = target.getvalue()
    assert "Unrecognized argument" in error
    assert "Perhaps you meant:" in error
    assert error.count("--reward.track") == 1
    assert "[...]" in error
    assert error.count("--help") == 5


def test_similar_arguments_subcommands_overflow_same_startswith_multiple() -> None:
    @dataclasses.dataclass
    class RewardConfig:
        track: bool

    @dataclasses.dataclass
    class ClassA:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassB:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassC:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassD:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassE:
        reward: RewardConfig
        rewarde: tyro.conf.Suppress[int] = 10

    @dataclasses.dataclass
    class ClassF:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassG:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassH:
        reward: RewardConfig

    @dataclasses.dataclass
    class ClassI:
        reward: RewardConfig

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(  # type: ignore
            Union[
                ClassA, ClassB, ClassC, ClassD, ClassE, ClassF, ClassG, ClassH, ClassI
            ],
            args="--track --ffff".split(" "),
        )

    error = target.getvalue()
    assert "Unrecognized argument" in error
    assert "Arguments similar to --track" in error
    assert error.count("--rewar") == 1
    assert "rewarde" not in error
    assert "[...]" in error
    assert error.count("--help") == 5


def test_similar_flag() -> None:
    @dataclasses.dataclass
    class Args:
        flag: bool = False

    target = io.StringIO()
    with pytest.raises(SystemExit), contextlib.redirect_stdout(target):
        tyro.cli(
            Args,
            args="--lag".split(" "),
        )

    error = target.getvalue()

    # We don't print usage text anymore.
    assert error.count("--flag | --no-flag") == 0

    # Printed in the similar argument list.
    assert error.count("--flag, --no-flag") == 1


def test_value_error() -> None:
    """https://github.com/brentyi/tyro/issues/86"""

    def main() -> None:
        raise ValueError("This shouldn't be caught by tyro")

    with pytest.raises(ValueError):
        tyro.cli(main, args=[])


def test_value_error_subcommand() -> None:
    """https://github.com/brentyi/tyro/issues/86"""

    def main1() -> None:
        raise ValueError("This shouldn't be caught by tyro")

    def main2() -> None:
        raise ValueError("This shouldn't be caught by tyro")

    with pytest.raises(ValueError):
        tyro.extras.subcommand_cli_from_dict(
            {"main1": main1, "main2": main2}, args=["main1"]
        )


def test_wrong_annotation() -> None:
    @dataclasses.dataclass
    class Args:
        x: dict = None  # type: ignore

    with pytest.warns(UserWarning):
        assert tyro.cli(Args, args=[]).x is None
    with pytest.warns(UserWarning):
        assert tyro.cli(Args, args="--x key value k v".split(" ")).x == {
            "key": "value",
            "k": "v",
        }
