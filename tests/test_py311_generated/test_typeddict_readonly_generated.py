from typing import TypedDict

import pytest
from typing_extensions import ReadOnly

import tyro


def test_read_only_typeddict() -> None:
    class ManyTypesTypedDict(TypedDict):
        i: ReadOnly[int]  # type: ignore
        s: ReadOnly[ReadOnly[str]]  # type: ignore

    assert tyro.cli(
        ManyTypesTypedDict,
        args="--i 5 --s 5".split(" "),
    ) == dict(i=5, s="5")

    with pytest.raises(SystemExit):
        tyro.cli(ManyTypesTypedDict, args="--i 5".split(" "))

    with pytest.raises(SystemExit):
        tyro.cli(ManyTypesTypedDict, args="--s 5".split(" "))
