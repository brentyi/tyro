import dataclasses
from typing import Literal


@dataclasses.dataclass
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


@dataclasses.dataclass
class EnvironmentConfig:
    env_name: str = "HalfCheetah-v4"
    env_seed: int = 0
    env_num_threads: int = 1
    env_max_episode_steps: int = 1000
    env_action_repeat: int = 1
    env_frame_stack: int = 1
    env_observation_normalization: bool = True
    env_reward_normalization: bool = True


@dataclasses.dataclass
class RewardConfig:
    reward_scale: float = 1.0
    reward_shift: float = 0.0
    reward_normalization: bool = True
    reward_clip: float = 10.0


@dataclasses.dataclass
class LoggingConfig:
    log_dir: str = "logs"
    log_interval: int = 1000
    save_model_interval: int = 10000
    eval_interval: int = 5000
    eval_episodes: int = 10
    tensorboard_log: bool = True
