import contextlib
import copy
import dataclasses
import io
import pathlib
from collections import namedtuple
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


def test_collections_namedtuple_with_default() -> None:
    """Test that collections.namedtuple works with tyro.cli when default is provided."""
    SomeType = namedtuple("SomeType", ("field1", "field2", "field3"))

    # With a default value, tyro can infer types (int in this case)
    assert tyro.cli(
        SomeType,
        default=SomeType(0, 1, 2),
        args=["--field1", "3", "--field2", "4"],
    ) == SomeType(3, 4, 2)

    # Test with a mix of different types in default
    MixedType = namedtuple("MixedType", ("int_field", "str_field", "float_field"))
    assert tyro.cli(
        MixedType,
        default=MixedType(42, "hello", 3.14),
        args=["--int_field", "123", "--float_field", "2.718"],
    ) == MixedType(123, "hello", 2.718)


def test_collections_namedtuple_no_default_error() -> None:
    """Test that collections.namedtuple without default value raises the expected error."""
    SomeType = namedtuple("SomeType", ("field1", "field2", "field3"))

    # Without a default value, tyro can't infer types and should raise an error
    with pytest.raises(tyro.constructors.UnsupportedTypeAnnotationError):
        tyro.cli(
            SomeType,
            args=["--field1", "3", "--field2", "4", "--field3", "5"],
        )


def test_collections_namedtuple_with_defaults() -> None:
    """Test collections.namedtuple with _field_defaults dictionary."""
    # Create a namedtuple with defaults
    SomeTypeWithDefaults = namedtuple(
        "SomeTypeWithDefaults", ["field1", "field2", "field3"], defaults=(0, "default")
    )

    # The _field_defaults dict is automatically populated
    assert hasattr(SomeTypeWithDefaults, "_field_defaults")
    assert SomeTypeWithDefaults._field_defaults == {"field2": 0, "field3": "default"}

    # We need to provide a full instance as the default
    # The field defaults just populate _field_defaults dict but tyro still needs a default instance
    assert tyro.cli(
        SomeTypeWithDefaults,
        default=SomeTypeWithDefaults(5, 5, "default"),
        args=["--field1", "10", "--field2", "20"],
    ) == SomeTypeWithDefaults(10, 20, "default")


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


def test_functional_typeddict():
    """Source: https://github.com/brentyi/tyro/issues/87"""
    NerfMLPHiddenLayers_0 = TypedDict(
        "NerfMLPHiddenLayers_0",
        {
            "hidden_layers.0": int,
            "hidden_layers.1": int,
            "hidden_layers.2": int,
            "hidden_layers.3": int,
            "hidden_layers.4": int,
            "hidden_layers.5": int,
            "hidden_layers.6": int,
            "hidden_layers.7": int,
        },
    )
    NerfMLPHiddenLayers_1 = TypedDict(
        "NerfMLPHiddenLayers_1",
        {
            "hidden_layers.0": NotRequired[int],
            "hidden_layers.1": NotRequired[int],
            "hidden_layers.2": NotRequired[int],
            "hidden_layers.3": NotRequired[int],
            "hidden_layers.4": NotRequired[int],
            "hidden_layers.5": NotRequired[int],
            "hidden_layers.6": NotRequired[int],
            "hidden_layers.7": NotRequired[int],
        },
    )
    NerfMLPHiddenLayers_2 = TypedDict(
        "NerfMLPHiddenLayers_2",
        {
            "hidden_layers.0": int,
            "hidden_layers.1": int,
            "hidden_layers.2": int,
            "hidden_layers.3": int,
            "hidden_layers.4": int,
            "hidden_layers.5": int,
            "hidden_layers.6": int,
            "hidden_layers.7": int,
        },
        total=False,
    )
    with pytest.raises(SystemExit):
        tyro.cli(NerfMLPHiddenLayers_0, args=["--hidden_layers.0", "3"])
    assert tyro.cli(NerfMLPHiddenLayers_1, args=["--hidden_layers.0", "3"]) == {
        "hidden_layers.0": 3
    }
    assert tyro.cli(NerfMLPHiddenLayers_2, args=["--hidden_layers.0", "3"]) == {
        "hidden_layers.0": 3
    }


def test_not_required_bool() -> None:
    class NotRequiredBool(TypedDict):
        x: NotRequired[bool]

    assert tyro.cli(NotRequiredBool, args="--x".split(" ")) == {"x": True}
    assert tyro.cli(NotRequiredBool, args="--no-x".split(" ")) == {"x": False}
    assert tyro.cli(NotRequiredBool, args=[]) == {}


def test_functional_typeddict_with_default():
    """Source: https://github.com/brentyi/tyro/issues/87"""
    NerfMLPHiddenLayers_0 = TypedDict(
        "NerfMLPHiddenLayers_0",
        {
            "hidden_layers.0": int,
            "hidden_layers.1": int,
            "hidden_layers.2": int,
            "hidden_layers.3": int,
            "hidden_layers.4": int,
            "hidden_layers.5": int,
            "hidden_layers.6": int,
            "hidden_layers.7": int,
        },
    )
    NerfMLPHiddenLayers_1 = TypedDict(
        "NerfMLPHiddenLayers_1",
        {
            "hidden_layers.0": NotRequired[int],
            "hidden_layers.1": NotRequired[int],
            "hidden_layers.2": NotRequired[int],
            "hidden_layers.3": NotRequired[int],
            "hidden_layers.4": NotRequired[int],
            "hidden_layers.5": NotRequired[int],
            "hidden_layers.6": NotRequired[int],
            "hidden_layers.7": NotRequired[int],
        },
    )
    NerfMLPHiddenLayers_2 = TypedDict(
        "NerfMLPHiddenLayers_2",
        {
            "hidden_layers.0": int,
            "hidden_layers.1": int,
            "hidden_layers.2": int,
            "hidden_layers.3": int,
            "hidden_layers.4": int,
            "hidden_layers.5": int,
            "hidden_layers.6": int,
            "hidden_layers.7": int,
        },
        total=False,
    )
    with pytest.raises(SystemExit):
        tyro.cli(NerfMLPHiddenLayers_0, args=["--hidden_layers.0", "3"], default={})
    assert tyro.cli(
        NerfMLPHiddenLayers_1, args=["--hidden_layers.0", "3"], default={}
    ) == {"hidden_layers.0": 3}
    assert tyro.cli(
        NerfMLPHiddenLayers_2, args=["--hidden_layers.0", "3"], default={}
    ) == {"hidden_layers.0": 3}
