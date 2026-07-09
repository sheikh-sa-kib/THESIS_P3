"""DecisionEngine — tick-based evaluation of policies.

Design (Decision 1 — approved)
-------------------------------
The Decision Engine should evaluate once per simulation tick.

Simulation Tick
↓
Collect Observations
↓
Evaluate Policies
↓
Generate Decision
↓
Execute Decision (future)
↓
Advance Simulation

This guarantees deterministic replay.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from e3hybrid.decision.aggregation import DecisionAggregationPolicy
    from e3hybrid.decision.config import DecisionConfig
    from e3hybrid.decision.decision import Decision
    from e3hybrid.decision.decision_log import DecisionLog
    from e3hybrid.decision.observation import VehicleObservation
    from e3hybrid.decision.observation_assembler import ObservationAssembler
    from e3hybrid.decision.policy import DecisionPolicy
    from e3hybrid.decision.policy_registry import PolicyManager
    from e3hybrid.decision.validation import DecisionValidator


@dataclass(frozen=True, slots=True)
class DecisionEngineConfig:
    """Configuration for the Decision Engine."""

    config: DecisionConfig
    enable_validation: bool = True
    enable_logging: bool = True


class DecisionEngine:
    """Evaluates policies once per simulation tick and produces decisions.

    The engine is the central coordinator for the decision-making process:
    1. Receives a VehicleObservation from the ObservationAssembler.
    2. Evaluates all enabled policies.
    3. Aggregates recommendations via DecisionAggregationPolicy.
    4. Validates the resulting Decision.
    5. Logs the Decision to CSV.
    6. Returns the Decision for execution.

    The engine is completely unaware of which routing algorithm produced
    candidate routes.  It evaluates only on objective values.
    """

    def __init__(
        self,
        config: DecisionEngineConfig,
        policy_manager: PolicyManager,
        observation_assembler: ObservationAssembler,
        decision_log: DecisionLog | None = None,
        validator: DecisionValidator | None = None,
        aggregator: DecisionAggregationPolicy | None = None,
    ) -> None:
        """Initialize the Decision Engine.

        Parameters
        ----------
        config:
            Engine configuration.
        policy_manager:
            Manages policy instances.
        observation_assembler:
            Assembles VehicleObservation snapshots.
        decision_log:
            CSV decision logger.  If None and enable_logging=True, logging is skipped.
        validator:
            Decision validator.  If None and enable_validation=True, a default is used.
        aggregator:
            Recommendation aggregator.  If None, a default is used.
        """
        self._config = config
        self._policy_manager = policy_manager
        self._observation_assembler = observation_assembler
        self._decision_log = decision_log
        self._validator = validator if validator is not None else DecisionValidator()
        self._aggregator = aggregator if aggregator is not None else None  # Lazy import

    def evaluate(
        self,
        observation: VehicleObservation,
    ) -> Decision:
        """Evaluate policies and produce a decision for one vehicle.

        This is called exactly once per simulation tick per vehicle.

        Parameters
        ----------
        observation:
            VehicleObservation snapshot assembled by ObservationAssembler.

        Returns
        -------
        Decision
            The final decision for this evaluation cycle.

        Raises
        ------
        DecisionError
            If validation fails and enable_validation=True.
        """
        # Step 1: Evaluate all enabled policies.
        recommendations = self._evaluate_policies(observation)

        # Step 2: Aggregate recommendations.
        decision = self._aggregate_recommendations(
            observation.vehicle_id,
            observation.sim_time_s,
            recommendations,
        )

        # Step 3: Validate decision.
        if self._config.enable_validation:
            report = self._validator.validate(decision)
            if not report.is_valid:
                from e3hybrid.core.exceptions import DecisionError
                raise DecisionError(
                    f"Decision validation failed for vehicle {observation.vehicle_id}: "
                    f"{report}"
                )

        # Step 4: Log decision.
        if self._config.enable_logging and self._decision_log is not None:
            self._decision_log.log(decision)

        return decision

    def _evaluate_policies(
        self, observation: VehicleObservation
    ) -> tuple[object, ...]:  # tuple[PolicyRecommendation, ...]
        """Evaluate all enabled policies on the observation.

        Policies are evaluated in registration order.  Each policy returns
        exactly one PolicyRecommendation.  Policies never raise exceptions;
        they return a low-confidence KEEP_CURRENT_ROUTE recommendation when
        they have no opinion.
        """
        enabled_policies = self._policy_manager.get_enabled_policies()
        recommendations: list[object] = []  # List[PolicyRecommendation]

        for policy in enabled_policies:
            try:
                recommendation = policy.evaluate(observation)
                recommendations.append(recommendation)
            except Exception as e:
                # Policy failed to evaluate — log and continue with fallback.
                # In production, this should be logged.  For now, we skip.
                from e3hybrid.decision.policy import PolicyRecommendation
                from e3hybrid.decision.types import DecisionType
                fallback = PolicyRecommendation(
                    decision_type=DecisionType.KEEP_CURRENT_ROUTE,
                    priority=0,
                    confidence=0.0,
                    explanation=(
                        f"Policy '{policy.name}' raised exception: {e}. "
                        f"Using fallback recommendation."
                    ),
                    policy_name=policy.name,
                    veto=False,
                )
                recommendations.append(fallback)

        return tuple(recommendations)

    def _aggregate_recommendations(
        self,
        vehicle_id: object,  # VehicleId
        sim_time_s: float,
        recommendations: tuple[object, ...],  # tuple[PolicyRecommendation, ...]
    ) -> Decision:
        """Aggregate policy recommendations into a final Decision."""
        # Lazy import to avoid circular dependency.
        if self._aggregator is None:
            from e3hybrid.decision.aggregation import DecisionAggregationPolicy
            self._aggregator = DecisionAggregationPolicy()

        return self._aggregator.aggregate(
            vehicle_id=vehicle_id,
            sim_time_s=sim_time_s,
            recommendations=recommendations,
        )

    def get_enabled_policy_names(self) -> tuple[str, ...]:
        """Return names of all enabled policies."""
        return self._policy_manager.list_enabled()

    def get_available_policy_names(self) -> tuple[str, ...]:
        """Return names of all available policies."""
        return self._policy_manager.list_available()
