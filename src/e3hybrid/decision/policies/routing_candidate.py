"""RoutingCandidatePolicy — evaluate routing candidates on objective cost only.

The algorithm name is used ONLY for logging.  Cost comparison is entirely
on RouteCandidate.total_cost.  This ensures fair comparison between Dijkstra,
A*, ACO, BCO, PSO, and E³-Hybrid.

Phase 6: NullRouteCandidateSource returns empty candidates.  This policy
returns KEEP_CURRENT_ROUTE with low confidence when no candidates are available.
"""

from __future__ import annotations

from e3hybrid.decision.config import DecisionConfig
from e3hybrid.decision.observation import VehicleObservation
from e3hybrid.decision.policy import PolicyRecommendation
from e3hybrid.decision.types import DecisionType


class RoutingCandidatePolicy:
    """Compare candidate routes to current route — priority 40."""

    name: str = "routing_candidate"

    def __init__(self, config: DecisionConfig) -> None:
        self._config = config

    @property
    def enabled(self) -> bool:
        return self._config.routing.enabled

    def evaluate(self, observation: VehicleObservation) -> PolicyRecommendation:
        """Recommend reroute when a significantly better candidate exists."""

        cfg = self._config.routing
        candidates = observation.routing_candidates

        if not candidates:
            return PolicyRecommendation(
                decision_type=DecisionType.KEEP_CURRENT_ROUTE,
                priority=40,
                confidence=0.5,
                explanation=(
                    "No routing candidates available "
                    "(NullRouteCandidateSource in Phase 6). "
                    "Keeping current route."
                ),
                policy_name=self.name,
                veto=False,
            )

        current = observation.current_route
        if current is None:
            best = min(candidates, key=lambda c: c.total_cost)
            return PolicyRecommendation(
                decision_type=DecisionType.REQUEST_REROUTE,
                priority=40,
                confidence=0.9,
                explanation=(
                    f"No current route set. Best candidate "
                    f"(cost={best.total_cost:.2f}, algorithm={best.algorithm}) "
                    f"available — requesting adoption."
                ),
                policy_name=self.name,
                veto=False,
                payload={"route_id": str(best.route_id)},
            )

        best = min(candidates, key=lambda c: c.total_cost)
        improvement = (
            current.estimated_remaining_cost - best.total_cost
        ) / max(current.estimated_remaining_cost, 1e-9)

        if improvement >= cfg.improvement_threshold:
            return PolicyRecommendation(
                decision_type=DecisionType.REQUEST_REROUTE,
                priority=40,
                confidence=min(0.99, improvement),
                explanation=(
                    f"Candidate route '{best.route_id}' offers "
                    f"{improvement:.1%} improvement over current route "
                    f"(current={current.estimated_remaining_cost:.2f}, "
                    f"candidate={best.total_cost:.2f}, "
                    f"algorithm={best.algorithm})."
                ),
                policy_name=self.name,
                veto=False,
                payload={"route_id": str(best.route_id)},
            )

        return PolicyRecommendation(
            decision_type=DecisionType.KEEP_CURRENT_ROUTE,
            priority=40,
            confidence=1.0 - improvement,
            explanation=(
                f"Best candidate offers only "
                f"{improvement:.1%} improvement (threshold="
                f"{cfg.improvement_threshold:.0%}). "
                f"Keeping current route."
            ),
            policy_name=self.name,
            veto=False,
        )
