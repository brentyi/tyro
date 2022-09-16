import contextlib
import dataclasses
import io
import pathlib
from typing import Any, Dict, Mapping, NamedTuple, Tuple, Union, cast

import pytest
from typing_extensions import Literal, TypedDict

import dcargs
import dcargs._strings


def test_basic_dict():
    def main(params: Dict[str, int]) -> Dict[str, int]:
        return params

    assert dcargs.cli(main, args="--params hey 5 hello 2".split(" ")) == {
        "hey": 5,
        "hello": 2,
    }
    assert dcargs.cli(main, args="--params hey 5 hello 2".split(" ")) == {
        "hey": 5,
        "hello": 2,
    }
    with pytest.raises(SystemExit):
        dcargs.cli(main, args="--params hey 5 hello hey".split(" "))
    with pytest.raises(SystemExit):
        dcargs.cli(main, args="--params hey 5 hello".split(" "))
    with pytest.raises(SystemExit):
        dcargs.cli(main, args="--params".split(" "))


def test_dict_with_default():
    def main(params: Mapping[Literal[1, 3, 5, 7], bool] = {5: False, 1: True}) -> Any:
        return params

    assert dcargs.cli(main, args=[]) == {5: False, 1: True}
    assert dcargs.cli(main, args="--params.5 --params.no-1".split(" ")) == {
        5: True,
        1: False,
    }
    with pytest.raises(SystemExit):
        dcargs.cli(main, args="--params".split(" "))


def test_tuple_in_dict():
    def main(x: Dict[Union[Tuple[int, int], Tuple[str, str]], Tuple[int, int]]) -> dict:
        return x

    assert dcargs.cli(main, args="--x 1 1 2 2 3 3 4 4".split(" ")) == {
        (1, 1): (2, 2),
        (3, 3): (4, 4),
    }


def test_basic_typeddict():
    class ManyTypesTypedDict(TypedDict):
        i: int
        s: str

    assert dcargs.cli(
        ManyTypesTypedDict,
        args="--i 5 --s 5".split(" "),
    ) == dict(i=5, s="5")

    with pytest.raises(SystemExit):
        dcargs.cli(ManyTypesTypedDict, args="--i 5".split(" "))

    with pytest.raises(SystemExit):
        dcargs.cli(ManyTypesTypedDict, args="--s 5".split(" "))


def test_total_false_typeddict():
    class ManyTypesTypedDict(TypedDict, total=False):
        i: int
        s: str

    assert dcargs.cli(
        ManyTypesTypedDict,
        args="--i 5 --s 5".split(" "),
    ) == dict(i=5, s="5")

    assert dcargs.cli(ManyTypesTypedDict, args="--i 5".split(" ")) == dict(i=5)
    assert dcargs.cli(ManyTypesTypedDict, args="--s 5".split(" ")) == dict(s="5")


def test_total_false_nested_typeddict():
    class ChildTypedDict(TypedDict, total=False):
        i: int
        s: str

    class ParentTypedDict(TypedDict, total=False):
        child: ChildTypedDict

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.cli(
            ParentTypedDict,
            args="--child.i 5 --child.s 5".split(" "),
        )

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        assert (
            dcargs.cli(
                ParentTypedDict,
                args=[""],
            )
            == {}
        )


def test_total_false_typeddict_with_nested():
    @dataclasses.dataclass
    class Inner:
        j: float

    class ManyTypesTypedDict(TypedDict, total=False):
        i: int
        s: Inner

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.cli(
            ManyTypesTypedDict,
            args="".split(" "),
        )

    with pytest.raises(dcargs.UnsupportedTypeAnnotationError):
        dcargs.cli(
            ManyTypesTypedDict,
            args="--x.i 5 --x.s 5 5".split(" "),
        )


def test_total_false_typeddict_with_tuple():
    class ManyTypesTypedDict(TypedDict, total=False):
        i: int
        s: Tuple[str, str]

    assert (
        dcargs.cli(
            ManyTypesTypedDict,
            args=[],
        )
        == dict()
    )

    assert dcargs.cli(
        ManyTypesTypedDict,
        args="--i 5 --s 5 5".split(" "),
    ) == dict(i=5, s=("5", "5"))


def test_nested_typeddict():
    class ChildTypedDict(TypedDict):
        y: int

    class NestedTypedDict(TypedDict):
        x: int
        b: ChildTypedDict

    assert dcargs.cli(NestedTypedDict, args=["--x", "1", "--b.y", "3"]) == dict(
        x=1, b=dict(y=3)
    )
    with pytest.raises(SystemExit):
        dcargs.cli(NestedTypedDict, args=["--x", "1"])


def test_helptext_and_default_typeddict():
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
            dcargs.cli(HelptextTypedDict, default={"z": 3}, args=["--help"])
    helptext = dcargs._strings.strip_ansi_sequences(f.getvalue())
    assert cast(str, HelptextTypedDict.__doc__) in helptext
    assert "--x INT" in helptext
    assert "--y INT" in helptext
    assert "--z INT" in helptext
    assert "Documentation 1 (required)" in helptext
    assert "Documentation 2 (required)" in helptext
    assert "Documentation 3 (default: 3)" in helptext


def test_basic_namedtuple():
    class ManyTypesNamedTuple(NamedTuple):
        i: int
        s: str
        f: float
        p: pathlib.Path

    assert dcargs.cli(
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


def test_nested_namedtuple():
    class ChildNamedTuple(NamedTuple):
        y: int

    class NestedNamedTuple(NamedTuple):
        x: int
        b: ChildNamedTuple

    assert dcargs.cli(
        NestedNamedTuple, args=["--x", "1", "--b.y", "3"]
    ) == NestedNamedTuple(x=1, b=ChildNamedTuple(y=3))
    with pytest.raises(SystemExit):
        dcargs.cli(NestedNamedTuple, args=["--x", "1"])


def test_helptext_and_default_namedtuple():
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
            dcargs.cli(HelptextNamedTupleDefault, args=["--help"])
    helptext = dcargs._strings.strip_ansi_sequences(f.getvalue())
    assert cast(str, HelptextNamedTupleDefault.__doc__) in helptext
    assert "--x INT" in helptext
    assert "--y INT" in helptext
    assert "--z INT" in helptext
    assert "Documentation 1 (required)" in helptext
    assert "Documentation 2 (required)" in helptext
    assert "Documentation 3 (default: 3)" in helptext


def test_helptext_and_default_namedtuple_alternate():
    class HelptextNamedTuple(NamedTuple):
        """This docstring should be printed as a description."""

        x: int  # Documentation 1

        # Documentation 2
        y: int

        z: int
        """Documentation 3"""

    with pytest.raises(SystemExit):
        dcargs.cli(
            HelptextNamedTuple,
            default=dcargs.MISSING,
            args=[],
        )

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            dcargs.cli(
                HelptextNamedTuple,
                default=HelptextNamedTuple(
                    x=dcargs.MISSING,
                    y=dcargs.MISSING,
                    z=3,
                ),
                args=["--help"],
            )
    helptext = dcargs._strings.strip_ansi_sequences(f.getvalue())
    assert cast(str, HelptextNamedTuple.__doc__) in helptext
    assert "Documentation 1 (required)" in helptext
    assert "Documentation 2 (required)" in helptext
    assert "Documentation 3" in helptext
    assert "(default: 3)" in helptext
