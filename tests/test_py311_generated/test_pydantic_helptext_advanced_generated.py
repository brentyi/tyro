"""Adapted from: https://github.com/brentyi/tyro/issues/183"""

from typing import Annotated, NamedTuple, Set

from helptext_utils import get_helptext_with_checks
from pydantic import BaseModel, Field

import tyro


class MyRange(NamedTuple):
    low: int
    high: int

    def __str__(self):
        return f"<{self.low}, {self.high}>"

    @staticmethod
    def tyro_constructor(
        range_str: Annotated[
            str,
            tyro.conf.arg(name=""),
        ],
    ):
        import re

        m = re.match("([0-9]+)(-([0-9]+))*", range_str)
        low = m[1]  # type: ignore
        high = low if not m[3] else m[3]  # type: ignore

        return MyRange(int(low), int(high))

    @staticmethod
    def tyro_constructor_set(
        range_str_set: Annotated[
            Set[str],
            tyro.conf.arg(name=""),
        ],
    ):
        return {MyRange.tyro_constructor(r) for r in range_str_set}


class MySpec(BaseModel):
    some_set: Set[int] = Field(
        default={1, 2, 3},
        description="Some set of integers",
        title="Some set",
    )

    some_string: str = Field(
        description="Some string without a default value.", title="SomeSTR"
    )

    here_comes_the_trouble: Annotated[
        Set[MyRange],
        tyro.conf.arg(constructor=MyRange.tyro_constructor_set),
    ] = Field(
        default={MyRange(0, 1024)},
        description="I would like this one in the same group as others",
        title="Please help",
    )


def add_spec(spec: MySpec) -> MySpec:
    return spec


def test_functionality() -> None:
    assert tyro.cli(
        add_spec, args=["--spec.some-set", "1", "2", "3", "--spec.some-string", "hello"]
    ) == MySpec(
        some_set={1, 2, 3},
        some_string="hello",
        here_comes_the_trouble={MyRange(0, 1024)},
    )
    assert tyro.cli(
        add_spec,
        args=[
            "--spec.some-set",
            "1",
            "2",
            "3",
            "--spec.some-string",
            "hello",
            "--spec.here-comes-the-trouble",
            "0-512",
        ],
    ) == MySpec(
        some_set={1, 2, 3},
        some_string="hello",
        here_comes_the_trouble={MyRange(0, 512)},
    )


def test_helptext() -> None:
    helptext = get_helptext_with_checks(add_spec)
    assert "spec options" in helptext
    assert "spec.here-comes-the-trouble-options" not in helptext
