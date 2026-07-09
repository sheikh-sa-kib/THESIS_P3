"""DecisionAggregationPolicy — selects the winning recommendation.

Aggregation rules
-----------------
1. If ANY recommendation has ``veto=True``, the highest-priority veto wins
   unconditionally.  This enforces hard constraints (safety, emergency stop).
2. When no veto is present, the recommendation with the highest ``priority``
   wins.  Ties are broken by ``confidence`` descending.
3. If all policies return KEEP_CURRENT_ROUTE (or no recommendations are
   provided), KEEP_CURRENT_ROUTE is returned with full confidence.
4. The winning recommendation's explanation becomes the Decision.explanation.
   All recommendations are stored in Decision.all_recommendations for audit.
"""

from __future__ import annotations

from e3hybrid.decision.decision import Decision
from e3hybrid.decision.policy import PolicyRecommendation
from e3hybrid.decision.types import DecisionType
from e3hybrid.vehicle.types import VehicleId


class DecisionAggregationPolicy:
    """Selects the winning PolicyRecommendation from a complete evaluation set."""

    name: str = "aggregation"

    def aggregate(
        self,
        vehicle_id: VehicleId,
        sim_time_s: float,
        recommendations: tuple[PolicyRecommendation, ...],
    ) -> Decision:
        """Return the final Decision for one evaluation cycle.

        Parameters
        ----------
        vehicle_id:
            The vehicle being evaluated.
        sim_time_s:
            Current simulation clock.
        recommendations:
            All PolicyRecommendation objects produced by enabled policies.
            May be empty — safe fallback to KEEP_CURRENT_ROUTE.
        """
        if not recommendations:
            return self._fallback(vehicle_id, sim_time_s, recommendations)

        applied = tuple(r.policy_name for r in recommendations)

        # Rule 1: veto takes precedence.
        vetoes = [r for r in recommendations if r.veto]
        if vetoes:
            winner = max(vetoes, key=lambda r: (r.priority, r.confidence))
            return Decision.create(
                vehicle_id=vehicle_id,
                sim_time_s=sim_time_s,
                decision_type=winner.decision_type,
                trigger=f"veto:{winner.policy_name}",
                explanation=winner.explanation,
                winning_policy=winner.policy_name,
                applied_policies=applied,
                recommendations=recommendations,
                veto=True,
                confidence=winner.confidence,
                payload=winner.payload,
            )

        # Rule 2: highest priority, confidence as tiebreaker.
        winner = max(recommendations, key=lambda r: (r.priority, r.confidence))
        return Decision.create(
            vehicle_id=vehicle_id,
            sim_time_s=sim_time_s,
            decision_type=winner.decision_type,
            trigger=winner.policy_name,
            explanation=winner.explanation,
            winning_policy=winner.policy_name,
            applied_policies=applied,
            recommendations=recommendations,
            veto=False,
            confidence=winner.confidence,
            payload=winner.payload,
        )

    def _fallback(
        self,
        vehicle_id: VehicleId,
        sim_time_s: float,
        recommendations: tuple[PolicyRecommendation, ...],
    ) -> Decision:
        """Return KEEP_CURRENT_ROUTE when no recommendations exist."""
        return Decision.create(
            vehicle_id=vehicle_id,
            sim_time_s=sim_time_s,
            decision_type=DecisionType.KEEP_CURRENT_ROUTE,
            trigger="no_recommendations",
            explanation="No policies produced recommendations. Keeping current route.",
            winning_policy="fallback",
            applied_policies=(),
            recommendations=recommendations,
            veto=False,
            confidence=1.0,
        )
