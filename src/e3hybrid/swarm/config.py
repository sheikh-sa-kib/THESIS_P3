"""SwarmConfig — configuration for a swarm optimization run."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from e3hybrid.routing.cost_calculator import CostWeights


@dataclass(frozen=True, slots=True)
class SwarmConfig:
    """Configuration for a swarm optimization run.

    Algorithm-specific hyperparameters are stored in the generic
    hyperparameters dict, keeping the config structure algorithm-agnostic.

    Parameters
    ----------
    algorithm_name:
        Name of the swarm algorithm (e.g., "aco", "bco", "pso").
    population_size:
        Number of individuals in the swarm population.
    max_iterations:
        Maximum number of optimization iterations.
    time_limit_s:
        Maximum wall-clock time in seconds (0 = no limit).
    convergence_threshold:
        Stop when |best_score - previous_best_score| < threshold
        for `stall_limit` consecutive iterations.
    stall_limit:
        Number of iterations without improvement before convergence.
    target_score:
        Stop when best_score <= target_score (0 = no target).
    seed:
        Random seed for reproducibility.
    hyperparameters:
        Algorithm-specific parameters stored as generic key-value pairs.
    cost_weights:
        Weights for cost components used in fitness evaluation.
    """

    algorithm_name: str = ""
    population_size: int = 10
    max_iterations: int = 100
    time_limit_s: float = 0.0
    convergence_threshold: float = 0.0
    stall_limit: int = 10
    target_score: float = 0.0
    seed: int = 42
    hyperparameters: Mapping[str, object] = field(default_factory=dict)
    cost_weights: CostWeights = field(default_factory=lambda: CostWeights(  # type: ignore
        distance=1.0, time=0.0, energy=0.0, congestion=0.0,
        hazard=0.0, emergency=0.0, communication=0.0,
    ))

    def __post_init__(self) -> None:
        if self.population_size < 1:
            raise ValueError("population_size must be positive")
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be positive")
        if self.time_limit_s < 0:
            raise ValueError("time_limit_s must be non-negative")
        if self.convergence_threshold < 0:
            raise ValueError("convergence_threshold must be non-negative")
        if self.stall_limit < 0:
            raise ValueError("stall_limit must be non-negative")
        if self.target_score < 0:
            raise ValueError("target_score must be non-negative")
