import dataclasses
import time
from typing import Annotated

import tyro
import tyro._cli


# Define AlgorithmConfig locally if configs module is not available
@dataclasses.dataclass
class AlgorithmConfig:
    flow_steps: int = 1


def main(n: int = 5) -> None:
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

    start = time.perf_counter()

    # tyro._cli.enable_timing(True)  # This function doesn't exist
    try:
        tyro.cli(ExperimentConfig, args=["--help"])
    except SystemExit:
        pass

    print(f"Total time taken: {time.perf_counter() - start:.2f} seconds")


if __name__ == "__main__":
    tyro.cli(main)
