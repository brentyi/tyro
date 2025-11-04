import dataclasses
import time
from typing import Annotated, Literal

import tyro


@dataclasses.dataclass(frozen=True)
class AlgorithmConfig:
    flow_steps: int = 10
    output_mode: Literal["u", "u_but_supervise_as_eps"] = "u_but_supervise_as_eps"
    timestep_embed_dim: int = 8
    n_samples_per_action: int = 8
    average_losses_before_exp: bool = True
    discretize_t_for_training: bool = True
    feather_std: float = 0.0
    policy_mlp_output_scale: float = 0.25
    trust_region_mode: Literal["ppo", "spo"] = "ppo"
    loss_mode: Literal["fpo", "denoising_mdp"] = "fpo"
    final_steps_only: bool = False
    sde_sigma: float = 0.0
    clipping_epsilon: float = 0.05
    batch_size: int = 1024
    discounting: float = 0.995
    episode_length: int = 1000
    learning_rate: float = 3e-4
    normalize_observations: bool = True
    num_envs: int = 2048
    num_evals: int = 10
    num_minibatches: int = 32
    num_timesteps: int = 60_000_000
    num_updates_per_batch: int = 16
    reward_scaling: float = 10.0
    unroll_length: int = 30
    gae_lambda: float = 0.95
    normalize_advantage: bool = True
    value_loss_coeff: float = 0.25


@dataclasses.dataclass(frozen=True)
class EnvironmentConfig:
    env_name: str = "HalfCheetah-v4"
    env_seed: int = 0
    env_num_threads: int = 1
    env_max_episode_steps: int = 1000
    env_action_repeat: int = 1
    env_frame_stack: int = 1
    env_observation_normalization: bool = True
    env_reward_normalization: bool = True


@dataclasses.dataclass(frozen=True)
class RewardConfig:
    reward_scale: float = 1.0
    reward_shift: float = 0.0
    reward_normalization: bool = True
    reward_clip: float = 10.0


@dataclasses.dataclass(frozen=True)
class LoggingConfig:
    log_dir: str = "logs"
    log_interval: int = 1000
    save_model_interval: int = 10000
    eval_interval: int = 5000
    eval_episodes: int = 10
    tensorboard_log: bool = True


def main(n: int = 5) -> None:
    @dataclasses.dataclass(frozen=True)
    class ExperimentConfig:
        algorithm: Annotated[
            AlgorithmConfig,
            tyro.conf.arg(
                constructor=tyro.extras.subcommand_type_from_defaults(
                    {str(i): AlgorithmConfig(flow_steps=i) for i in range(n)}
                )
            ),
        ] = AlgorithmConfig()
        env: Annotated[
            EnvironmentConfig,
            tyro.conf.arg(
                constructor=tyro.extras.subcommand_type_from_defaults(
                    {str(i): EnvironmentConfig(env_name=f"Env-{i}") for i in range(n)}
                )
            ),
        ] = EnvironmentConfig()
        reward: Annotated[
            RewardConfig,
            tyro.conf.arg(
                constructor=tyro.extras.subcommand_type_from_defaults(
                    {str(i): RewardConfig(reward_scale=i) for i in range(n)}
                )
            ),
        ] = RewardConfig()
        logging: Annotated[
            LoggingConfig,
            tyro.conf.arg(
                constructor=tyro.extras.subcommand_type_from_defaults(
                    {str(i): LoggingConfig(log_dir=f"logs_{i}") for i in range(n)}
                )
            ),
        ] = LoggingConfig()
        logging2: Annotated[
            LoggingConfig,
            tyro.conf.arg(
                constructor=tyro.extras.subcommand_type_from_defaults(
                    {str(i): LoggingConfig(log_dir=f"logs_{i}") for i in range(n)}
                )
            ),
        ] = LoggingConfig()
        logging3: Annotated[
            LoggingConfig,
            tyro.conf.arg(
                constructor=tyro.extras.subcommand_type_from_defaults(
                    {str(i): LoggingConfig(log_dir=f"logs_{i}") for i in range(n)}
                )
            ),
        ] = LoggingConfig()

    start = time.perf_counter()

    tyro._experimental_options["enable_timing"] = True
    try:
        tyro.cli(ExperimentConfig, args=[])
    except SystemExit:
        pass
    finally:
        tyro._experimental_options["enable_timing"] = False

    print(f"Total time taken: {time.perf_counter() - start:.2f} seconds")


if __name__ == "__main__":
    tyro.cli(main)
