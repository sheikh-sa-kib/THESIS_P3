"""E³-Hybrid Swarm Infrastructure — common abstractions for all swarm algorithms.

This package provides the algorithm-agnostic framework that ACO, BCO, PSO,
and future swarm algorithms build upon. No algorithm-specific logic exists
at this level.

Design philosophy
-----------------
- All models are immutable (frozen dataclasses)
- Algorithm-agnostic throughout (no references to ACO, BCO, PSO, or E³-Hybrid)
- Protocol-based interfaces for dependency injection
- Deterministic random number generation via SwarmRandom
- Configurable termination conditions evaluated by framework
- Benchmarked through SwarmToRoutingAdapter (no BenchmarkRunner modifications)
"""

from e3hybrid.swarm.aco import (
    ACORouting,
    ACOFactory,
    ACOStatistics,
    ACOValidator,
    ACSConfiguration,
    Ant,
    AntColony,
    PheromoneMatrix,
    PheromoneUpdater,
    TransitionRule,
    VisibilityMatrix,
)
from e3hybrid.swarm.bco import (
    BCORouting,
    BCOConfiguration,
    BCOStatistics,
    BCOValidator,
    BackwardPassResult,
    BeeState,
    BeeStatus,
    ForwardPassResult,
    VisibilityCache,
)
from e3hybrid.swarm.pso import (
    PSORouting,
    PSOConfiguration,
    PSOStatistics,
    PSOValidator,
    ParticleState,
    ParticleStatus,
)
from e3hybrid.swarm.hybrid import (
    E3HybridRouting,
    HybridConfiguration,
    HybridStatistics,
    HybridInfluenceWeights,
    IndividualKind,
    IndividualState,
)
from e3hybrid.swarm.adapter import SwarmToRoutingAdapter
from e3hybrid.swarm.config import SwarmConfig
from e3hybrid.swarm.context import SwarmContext
from e3hybrid.swarm.factory import SwarmFactory
from e3hybrid.swarm.lifecycle import SwarmLifecycle
from e3hybrid.swarm.models import (
    CandidateSolution,
    OptimizationScore,
    Population,
    SearchState,
    Solution,
)
from e3hybrid.swarm.protocol import SwarmAlgorithm
from e3hybrid.swarm.random import SwarmRandom
from e3hybrid.swarm.result import SwarmResult
from e3hybrid.swarm.state import SwarmState
from e3hybrid.swarm.statistics import IterationStatistics, SwarmStatistics
from e3hybrid.swarm.termination import TerminationChecker, TerminationCondition
from e3hybrid.swarm.validator import SwarmValidationReport, SwarmValidator

__all__ = [
    # Protocol
    "SwarmAlgorithm",
    # Configuration
    "SwarmConfig",
    # ACO
    "ACSConfiguration",
    "PheromoneMatrix",
    "VisibilityMatrix",
    "TransitionRule",
    "PheromoneUpdater",
    "Ant",
    "AntColony",
    "ACOStatistics",
    "ACOValidator",
    "ACOFactory",
    "ACORouting",
    # BCO
    "BCOConfiguration",
    "BCOStatistics",
    "BCOValidator",
    "BCORouting",
    "BeeState",
    "BeeStatus",
    "BackwardPassResult",
    "ForwardPassResult",
    "VisibilityCache",
    # PSO
    "PSOConfiguration",
    "PSOStatistics",
    "PSOValidator",
    "PSORouting",
    "ParticleState",
    "ParticleStatus",
    # Context
    "SwarmContext",
    # State
    "SwarmState",
    # Models
    "Solution",
    "CandidateSolution",
    "OptimizationScore",
    "SearchState",
    "Population",
    # Statistics
    "SwarmStatistics",
    "IterationStatistics",
    # Result
    "SwarmResult",
    # Termination
    "TerminationCondition",
    "TerminationChecker",
    # Random
    "SwarmRandom",
    # Lifecycle
    "SwarmLifecycle",
    # Validation
    "SwarmValidator",
    "SwarmValidationReport",
    # Factory
    "SwarmFactory",
    # Adapter
    "SwarmToRoutingAdapter",
    # Hybrid
    "E3HybridRouting",
    "HybridConfiguration",
    "HybridStatistics",
    "HybridInfluenceWeights",
    "IndividualKind",
    "IndividualState",
]
