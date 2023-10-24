import dataclasses

import tyro


def test_dataclass_init_var() -> None:
    @dataclasses.dataclass
    class DataclassWithInitVar:
        i: dataclasses.InitVar[int]
        x: str

        def __post_init__(self, i: int) -> None:
            self.x += str(i)

    # We can directly pass a dataclass to `tyro.cli()`:
    assert (
        tyro.cli(
            DataclassWithInitVar,
            args=[
                "--i",
                "5",
                "--x",
                "5",
            ],
        ).x
        == "55"
    )
