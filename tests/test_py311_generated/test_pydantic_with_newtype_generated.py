from typing import Annotated, NewType, Tuple

import pydantic
from pydantic import BaseModel

import tyro

Microliter = NewType("Microliter", int)


class Measurements(BaseModel):
    single: Microliter = pydantic.Field(Microliter(10))
    renamed_single: Annotated[Microliter, tyro.conf.arg(name="other_single")] = (
        pydantic.Field(Microliter(10))
    )
    pair: Tuple[Microliter, Microliter] = pydantic.Field(
        (Microliter(20), Microliter(30))
    )


IncorrectMeasurements = NewType("IncorrectMeasurements", Measurements)


def test_pydantic_with_newtype():
    assert tyro.cli(
        IncorrectMeasurements, args="--single 1 --pair 2 3".split(" ")
    ) == Measurements(
        single=Microliter(1),
        renamed_single=Microliter(10),
        pair=(Microliter(2), Microliter(3)),
    )
    assert tyro.cli(
        IncorrectMeasurements, args="--single 1 --other-single 5".split(" ")
    ) == Measurements(
        single=Microliter(1),
        renamed_single=Microliter(5),
        pair=(Microliter(20), Microliter(30)),
    )
