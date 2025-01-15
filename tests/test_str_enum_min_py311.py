import enum

from pydantic import BaseModel, ConfigDict, Field

import tyro


class SomeEnum(enum.StrEnum):
    A = enum.auto()
    B = enum.auto()


def test_str_enum() -> None:
    def main(x: SomeEnum) -> SomeEnum:
        return x

    assert tyro.cli(main, args="--x A".split(" ")) == SomeEnum.A


def test_str_enum_value_config() -> None:
    def main(x: SomeEnum) -> SomeEnum:
        return x

    assert (
        tyro.cli(
            main, args="--x a".split(" "), config=(tyro.conf.EnumChoicesFromValues,)
        )
        == SomeEnum.A
    )


def test_str_enum_default() -> None:
    def main(x: SomeEnum = SomeEnum.A) -> SomeEnum:
        return x

    assert tyro.cli(main, args=[]) == SomeEnum.A
    assert tyro.cli(main, args="--x A".split(" ")) == SomeEnum.A


def test_pydantic() -> None:
    class Model(BaseModel):
        x: SomeEnum = Field(default=SomeEnum.A)

    assert tyro.cli(Model, args=[]).x == SomeEnum.A


def test_pydantic_use_enum_values() -> None:
    class Model(BaseModel):
        model_config = ConfigDict(use_enum_values=True)
        x: SomeEnum = Field(default=SomeEnum.A)

    # Check default value of `x`.
    assert SomeEnum.A == SomeEnum.A.value
    x = tyro.cli(
        Model,
        args=[],
        default=Model.model_validate({}),
    ).x
    assert x == SomeEnum.A == SomeEnum.A.value
    assert isinstance(x, str)
    assert not isinstance(x, SomeEnum)

    # Check default value of `x` with `EnumChoicesFromValues`.
    x = tyro.cli(
        Model,
        args=[],
        default=Model.model_validate({}),
        config=(tyro.conf.EnumChoicesFromValues,),
    ).x
    assert x == SomeEnum.A == SomeEnum.A.value
    assert isinstance(x, str)
    assert not isinstance(x, SomeEnum)

    # Pass some values in.
    x = tyro.cli(
        Model,
        args="--x A".split(" "),
        default=Model.model_validate({}),
    ).x
    assert x == "a"
    x = tyro.cli(
        Model,
        args="--x a".split(" "),
        default=Model.model_validate({}),
        config=(tyro.conf.EnumChoicesFromValues,),
    ).x
    assert x == SomeEnum.A
