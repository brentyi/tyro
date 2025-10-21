import dataclasses
import time
from typing import Annotated

from configs import AlgorithmConfig, EnvironmentConfig, LoggingConfig, RewardConfig

import tyro
import tyro._cli


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
        env: Annotated[
            EnvironmentConfig,
            tyro.conf.arg(
                constructor=tyro.extras.subcommand_type_from_defaults(
                    {str(i): EnvironmentConfig(env_name=f"Env-{i}") for i in range(n)}
                )
            ),
        ]
        reward: Annotated[
            RewardConfig,
            tyro.conf.arg(
                constructor=tyro.extras.subcommand_type_from_defaults(
                    {str(i): RewardConfig(reward_scale=i) for i in range(n)}
                )
            ),
        ]
        logging: Annotated[
            LoggingConfig,
            tyro.conf.arg(
                constructor=tyro.extras.subcommand_type_from_defaults(
                    {str(i): LoggingConfig(log_dir=f"logs_{i}") for i in range(n)}
                )
            ),
        ]
        logging2: Annotated[
            LoggingConfig,
            tyro.conf.arg(
                constructor=tyro.extras.subcommand_type_from_defaults(
                    {str(i): LoggingConfig(log_dir=f"logs_{i}") for i in range(n)}
                )
            ),
        ]
        logging3: Annotated[
            LoggingConfig,
            tyro.conf.arg(
                constructor=tyro.extras.subcommand_type_from_defaults(
                    {str(i): LoggingConfig(log_dir=f"logs_{i}") for i in range(n)}
                )
            ),
        ]

    start = time.perf_counter()

    tyro._cli.enable_timing(True)
    try:
        tyro.cli(ExperimentConfig, args=["--help"])
    except SystemExit:
        pass

    print(f"Total time taken: {time.perf_counter() - start:.2f} seconds")


if __name__ == "__main__":
    tyro.cli(main)
