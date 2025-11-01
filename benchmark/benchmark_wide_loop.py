import dataclasses
import time
from typing import Annotated

import tyro


# Define AlgorithmConfig locally if configs module is not available
@dataclasses.dataclass(frozen=True)
class AlgorithmConfig:
    flow_steps: int = 1


def main() -> None:
    n = 4000

    @dataclasses.dataclass
    class ExperimentConfig:
        algorithm: Annotated[
            AlgorithmConfig,
            tyro.conf.arg(
                constructor=tyro.extras.subcommand_type_from_defaults(
                    {str(i): AlgorithmConfig(flow_steps=i) for i in range(n)}
                )
            ),
        ]

    for _ in range(5):
        start = time.perf_counter()

        # tyro._cli.enable_timing(True)  # This function doesn't exist
        assert (
            tyro.cli(ExperimentConfig, args=["algorithm:100"]).algorithm.flow_steps
            == 100
        )

        print(f"Total time taken: {time.perf_counter() - start:.2f} seconds")


if __name__ == "__main__":
    tyro.cli(main)
