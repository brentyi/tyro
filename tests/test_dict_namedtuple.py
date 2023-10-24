import contextlib
import copy
import dataclasses
import io
import pathlib
from typing import Any, Dict, Mapping, NamedTuple, Tuple, Union, cast

import pytest
from typing_extensions import Literal, NotRequired, Required, TypedDict

import tyro
import tyro._strings


def test_basic_dict() -> None:
    def main(params: Dict[str, int]) -> Dict[str, int]:
        return params

    assert tyro.cli(main, args="--params hey 5 hello 2".split(" ")) == {
        "hey": 5,
        "hello": 2,
    }
    assert tyro.cli(main, args="--params hey 5 hello 2".split(" ")) == {
        "hey": 5,
        "hello": 2,
    }
    assert tyro.cli(main, args="--params".split(" ")) == {}
    with pytest.raises(SystemExit):
        tyro.cli(main, args="--params hey 5 hello hey".split(" "))
    with pytest.raises(SystemExit):
        tyro.cli(main, args="--params hey 5 hello".split(" "))


def test_dict_with_default() -> None:
    def main(params: Mapping[Literal[1, 3, 5, 7], bool] = {5: False, 1: True}) -> Any:
        return params

    assert tyro.cli(main, args=[]) == {5: False, 1: True}
    assert tyro.cli(main, args="--params.5 --params.no-1".split(" ")) == {
        5: True,
        1: False,
    }
    with pytest.raises(SystemExit):
        tyro.cli(main, args="--params".split(" "))


def test_tuple_in_dict() -> None:
    def main(x: Dict[Union[Tuple[int, int], Tuple[str, str]], Tuple[int, int]]) -> dict:
        return x

    assert tyro.cli(main, args="--x 1 1 2 2 3 3 4 4".split(" ")) == {
        (1, 1): (2, 2),
        (3, 3): (4, 4),
    }


def test_basic_typeddict() -> None:
    class ManyTypesTypedDict(TypedDict):
        i: int
        s: str

    assert tyro.cli(
        ManyTypesTypedDict,
        args="--i 5 --s 5".split(" "),
    ) == dict(i=5, s="5")

    with pytest.raises(SystemExit):
        tyro.cli(ManyTypesTypedDict, args="--i 5".split(" "))

    with pytest.raises(SystemExit):
        tyro.cli(ManyTypesTypedDict, args="--s 5".split(" "))


def test_positional_in_typeddict() -> None:
    class ManyTypesTypedDict(TypedDict):
        i: tyro.conf.Positional[int]
        s: str

    assert tyro.cli(
        ManyTypesTypedDict,
        args="5 --s 5".split(" "),
    ) == dict(i=5, s="5")

    with pytest.raises(SystemExit):
        tyro.cli(ManyTypesTypedDict, args="5".split(" "))

    with pytest.raises(SystemExit):
        tyro.cli(ManyTypesTypedDict, args="--s 5".split(" "))


def test_total_false_typeddict() -> None:
    class ManyTypesTypedDict(TypedDict, total=False):
        i: int
        s: str

    assert tyro.cli(
        ManyTypesTypedDict,
        args="--i 5 --s 5".split(" "),
    ) == dict(i=5, s="5")

    assert tyro.cli(ManyTypesTypedDict, args=[]) == dict()
    assert tyro.cli(ManyTypesTypedDict, args="--i 5".split(" ")) == dict(i=5)
    assert tyro.cli(ManyTypesTypedDict, args="--s 5".split(" ")) == dict(s="5")


def test_total_false_required_typeddict() -> None:
    class ManyTypesTypedDict(TypedDict, total=False):
        i: int
        s: Required[str]

    assert tyro.cli(
        ManyTypesTypedDict,
        args="--i 5 --s 5".split(" "),
    ) == dict(i=5, s="5")

    with pytest.raises(SystemExit):
        # `s` is Required[].
        assert tyro.cli(ManyTypesTypedDict, args="--i 5".split(" ")) == dict(i=5)
    assert tyro.cli(
        ManyTypesTypedDict, args="--i 5".split(" "), default={"s": "5"}
    ) == dict(i=5, s="5")
    assert tyro.cli(ManyTypesTypedDict, args="--s 5".split(" ")) == dict(s="5")


def test_total_true_not_required_typeddict() -> None:
    class ManyTypesTypedDict(TypedDict, total=True):
        i: NotRequired[int]
        s: str

    assert tyro.cli(
        ManyTypesTypedDict,
        args="--i 5 --s 5".split(" "),
    ) == dict(i=5, s="5")

    with pytest.raises(SystemExit):
        # `s` is Required[].
        assert tyro.cli(ManyTypesTypedDict, args="--i 5".split(" ")) == dict(i=5)
    assert tyro.cli(
        ManyTypesTypedDict, args="--i 5".split(" "), default={"s": "5"}
    ) == dict(i=5, s="5")
    assert tyro.cli(ManyTypesTypedDict, args="--s 5".split(" ")) == dict(s="5")


def test_total_false_nested_typeddict() -> None:
    class ChildTypedDict(TypedDict, total=False):
        i: int
        s: str

    class ParentTypedDict(TypedDict, total=False):
        child: ChildTypedDict

    assert tyro.cli(
        ParentTypedDict,
        args="--child.i 5 --child.s 5".split(" "),
    ) == {"child": {"i": 5, "s": "5"}}

    # total=False is ~ignored on the parent.
    assert tyro.cli(
        ParentTypedDict,
        args=[],
    ) == {"child": {}}


def test_total_false_typeddict_with_nested() -> None:
    @dataclasses.dataclass
    class Inner:
        j: float

    class ManyTypesTypedDict(TypedDict, total=False):
        i: int
        s: Inner

    # --s.j is (unfortunately) still required.
    with pytest.raises(SystemExit):
        tyro.cli(
            ManyTypesTypedDict,
            args="".split(" "),
        )

    assert tyro.cli(
        ManyTypesTypedDict,
        args="--s.j 5".split(" "),
    ) == {"s": Inner(5.0)}


def test_total_false_typeddict_with_tuple() -> None:
    class ManyTypesTypedDict(TypedDict, total=False):
        i: int
        s: Tuple[str, str]

    assert (
        tyro.cli(
            ManyTypesTypedDict,
            args=[],
        )
        == dict()
    )

    assert tyro.cli(
        ManyTypesTypedDict,
        args="--i 5 --s 5 5".split(" "),
    ) == dict(i=5, s=("5", "5"))


def test_nested_typeddict() -> None:
    class ChildTypedDict(TypedDict):
        y: int

    class NestedTypedDict(TypedDict):
        x: int
        b: ChildTypedDict

    assert tyro.cli(NestedTypedDict, args=["--x", "1", "--b.y", "3"]) == dict(
        x=1, b=dict(y=3)
    )
    with pytest.raises(SystemExit):
        tyro.cli(NestedTypedDict, args=["--x", "1"])


def test_helptext_and_default_typeddict() -> None:
    class HelptextTypedDict(TypedDict):
        """This docstring should be printed as a description."""

        x: int  # Documentation 1

        # Documentation 2
        y: int

        z: int
        """Documentation 3"""

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            tyro.cli(HelptextTypedDict, default={"z": 3}, args=["--help"])
    helptext = tyro._strings.strip_ansi_sequences(f.getvalue())
    assert cast(str, HelptextTypedDict.__doc__) in helptext
    assert "--x INT" in helptext
    assert "--y INT" in helptext
    assert "--z INT" in helptext
    assert "Documentation 1 (required)" in helptext
    assert "Documentation 2 (required)" in helptext
    assert "Documentation 3 (default: 3)" in helptext


def test_basic_namedtuple() -> None:
    class ManyTypesNamedTuple(NamedTuple):
        i: int
        s: str
        f: float
        p: pathlib.Path

    assert tyro.cli(
        ManyTypesNamedTuple,
        args=[
            "--i",
            "5",
            "--s",
            "5",
            "--f",
            "5",
            "--p",
            "~",
        ],
    ) == ManyTypesNamedTuple(i=5, s="5", f=5.0, p=pathlib.Path("~"))


def test_nested_namedtuple() -> None:
    class ChildNamedTuple(NamedTuple):
        y: int

    class NestedNamedTuple(NamedTuple):
        x: int
        b: ChildNamedTuple

    assert tyro.cli(
        NestedNamedTuple, args=["--x", "1", "--b.y", "3"]
    ) == NestedNamedTuple(x=1, b=ChildNamedTuple(y=3))
    with pytest.raises(SystemExit):
        tyro.cli(NestedNamedTuple, args=["--x", "1"])


def test_helptext_and_default_namedtuple() -> None:
    class HelptextNamedTupleDefault(NamedTuple):
        """This docstring should be printed as a description."""

        x: int  # Documentation 1

        # Documentation 2
        y: int

        z: int = 3
        """Documentation 3"""

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            tyro.cli(HelptextNamedTupleDefault, args=["--help"])
    helptext = tyro._strings.strip_ansi_sequences(f.getvalue())
    assert cast(str, HelptextNamedTupleDefault.__doc__) in helptext
    assert "--x INT" in helptext
    assert "--y INT" in helptext
    assert "--z INT" in helptext
    assert "Documentation 1 (required)" in helptext
    assert "Documentation 2 (required)" in helptext
    assert "Documentation 3 (default: 3)" in helptext


def test_helptext_and_default_namedtuple_alternate() -> None:
    class HelptextNamedTuple(NamedTuple):
        """This docstring should be printed as a description."""

        x: int  # Documentation 1

        # Documentation 2
        y: int

        z: int
        """Documentation 3"""

    with pytest.raises(SystemExit):
        tyro.cli(
            HelptextNamedTuple,
            default=tyro.MISSING,
            args=[],
        )

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            tyro.cli(
                HelptextNamedTuple,
                default=HelptextNamedTuple(
                    x=tyro.MISSING,
                    y=tyro.MISSING,
                    z=3,
                ),
                args=["--help"],
            )
    helptext = tyro._strings.strip_ansi_sequences(f.getvalue())
    assert cast(str, HelptextNamedTuple.__doc__) in helptext
    assert "Documentation 1 (required)" in helptext
    assert "Documentation 2 (required)" in helptext
    assert "Documentation 3" in helptext
    assert "(default: 3)" in helptext


def test_nested_dict() -> None:
    loaded_config = {
        "batch_size": 32,
        "optimizer": {
            "learning_rate": 1e-4,
            "epsilon": 1e-8,
            "scheduler": {"schedule_type": "constant"},
        },
    }
    backup_config = copy.deepcopy(loaded_config)
    overrided_config = tyro.cli(
        dict,
        default=loaded_config,
        args=[
            "--batch-size",
            "16",
            "--optimizer.scheduler.schedule_type",
            "exponential",
        ],
    )

    # Overridden config should be different from loaded config.
    assert overrided_config != loaded_config
    assert overrided_config["batch_size"] == 16
    assert overrided_config["optimizer"]["scheduler"]["schedule_type"] == "exponential"

    # Original loaded config should not be mutated.
    assert loaded_config == backup_config


def test_nested_dict_use_underscores() -> None:
    loaded_config = {
        "batch_size": 32,
        "optimizer": {
            "learning_rate": 1e-4,
            "epsilon": 1e-8,
            "scheduler": {"schedule_type": "constant"},
        },
    }
    backup_config = copy.deepcopy(loaded_config)
    overrided_config = tyro.cli(
        dict,
        default=loaded_config,
        args=[
            "--batch-size",
            "16",
            "--optimizer.scheduler.schedule-type",
            "exponential",
        ],
        use_underscores=True,
    )

    # Overridden config should be different from loaded config.
    assert overrided_config != loaded_config
    assert overrided_config["batch_size"] == 16
    assert overrided_config["optimizer"]["scheduler"]["schedule_type"] == "exponential"

    # Original loaded config should not be mutated.
    assert loaded_config == backup_config


def test_nested_dict_hyphen() -> None:
    # We do a lot of underscore <=> conversion in the code; this is just to make sure it
    # doesn't break anything!
    loaded_config = {
        "batch-size": 32,
        "optimizer": {
            "learning-rate": 1e-4,
            "epsilon": 1e-8,
            "scheduler": {"schedule-type": "constant"},
        },
    }
    backup_config = copy.deepcopy(loaded_config)
    overrided_config = tyro.cli(
        dict,
        default=loaded_config,
        args=[
            "--batch-size",
            "16",
            "--optimizer.scheduler.schedule-type",
            "exponential",
        ],
    )

    # Overridden config should be different from loaded config.
    assert overrided_config != loaded_config
    assert overrided_config["batch-size"] == 16
    assert overrided_config["optimizer"]["scheduler"]["schedule-type"] == "exponential"

    # Original loaded config should not be mutated.
    assert loaded_config == backup_config


def test_nested_dict_hyphen_use_underscores() -> None:
    # We do a lot of underscore <=> conversion in the code; this is just to make sure it
    # doesn't break anything!
    loaded_config = {
        "batch-size": 32,
        "optimizer": {
            "learning-rate": 1e-4,
            "epsilon": 1e-8,
            "scheduler": {"schedule-type": "constant"},
        },
    }
    backup_config = copy.deepcopy(loaded_config)
    overrided_config = tyro.cli(
        dict,
        default=loaded_config,
        args=[
            "--batch-size",
            "16",
            "--optimizer.scheduler.schedule-type",
            "exponential",
        ],
        use_underscores=True,
    )

    # Overridden config should be different from loaded config.
    assert overrided_config != loaded_config
    assert overrided_config["batch-size"] == 16
    assert overrided_config["optimizer"]["scheduler"]["schedule-type"] == "exponential"

    # Original loaded config should not be mutated.
    assert loaded_config == backup_config

    overrided_config = tyro.cli(
        dict,
        default=loaded_config,
        args=[
            "--batch_size",
            "16",
            "--optimizer.scheduler.schedule_type",
            "exponential",
        ],
        use_underscores=True,
    )

    # Overridden config should be different from loaded config.
    assert overrided_config != loaded_config
    assert overrided_config["batch-size"] == 16
    assert overrided_config["optimizer"]["scheduler"]["schedule-type"] == "exponential"

    # Original loaded config should not be mutated.
    assert loaded_config == backup_config


def test_nested_dict_annotations() -> None:
    loaded_config = {
        "optimizer": {
            "scheduler": {"schedule-type": "constant"},
        },
    }

    overrided_config = tyro.cli(
        dict,
        default=loaded_config,
        args=[
            "--optimizer.scheduler.schedule-type",
            "exponential",
        ],
    )
    assert overrided_config["optimizer"]["scheduler"]["schedule-type"] == "exponential"
    del overrided_config

    overrided_config = tyro.cli(
        Dict[str, Dict],
        default=loaded_config,
        args=[
            "--optimizer.scheduler.schedule-type",
            "exponential",
        ],
    )
    assert overrided_config["optimizer"]["scheduler"]["schedule-type"] == "exponential"
    del overrided_config

    overrided_config = tyro.cli(
        Dict[str, Dict[str, Dict]],
        default=loaded_config,
        args=[
            "--optimizer.scheduler.schedule-type",
            "exponential",
        ],
    )
    assert overrided_config["optimizer"]["scheduler"]["schedule-type"] == "exponential"
    del overrided_config
