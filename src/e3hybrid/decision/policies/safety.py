"""SafetyPolicy — highest-priority hard constraints.

Veto conditions (Decision.veto = True):
- Current route contains a blocked edge → REQUEST_REROUTE (veto)
- Speed exceeds max_speed_mps        → REDUCE_SPEED (veto)

These hard constraints can never be overridden by lower-priority policies.
"""

from __future__ import annotations

from e3hybrid.decision.config import DecisionConfig
from e3hybrid.decision.observation import VehicleObservation
from e3hybrid.decision.policy import PolicyRecommendation
from e3hybrid.decision.types import DecisionType


class SafetyPolicy:
    """Hard-constraint safety checks — priority 100."""

    name: str = "safety"

    def __init__(self, config: DecisionConfig) -> None:
        self._config = config

    @property
    def enabled(self) -> bool:
        return self._config.safety.enabled

    def evaluate(self, observation: VehicleObservation) -> PolicyRecommendation:
        """Check for blocked route edges or speed violations."""

        # Check 1: current route contains a blocked edge.
        route = observation.current_route
        if route is not None and route.has_blocked_edge:
            blocked = [
                str(eid) for eid in route.remaining_edge_ids
                if observation.graph_snapshot.is_blocked(eid)
            ]
            label = ", ".join(blocked[:3])
            return PolicyRecommendation(
                decision_type=DecisionType.REQUEST_REROUTE,
                priority=100,
                confidence=1.0,
                explanation=(
                    f"Blocked edge(s) detected on current route: [{label}]. "
                    f"Requesting reroute immediately."
                ),
                policy_name=self.name,
                veto=True,
                payload={"blocked_edge_ids": blocked},
            )

        # Check 2: speed violation.
        speed = observation.vehicle_state.speed_mps
        max_speed = observation.constraints.max_speed_mps
        if speed > max_speed:
            return PolicyRecommendation(
                decision_type=DecisionType.REDUCE_SPEED,
                priority=100,
                confidence=1.0,
                explanation=(
                    f"Speed {speed:.1f} m/s exceeds max_speed_mps "
                    f"{max_speed:.1f} m/s. Reducing speed."
                ),
                policy_name=self.name,
                veto=True,
                payload={"target_speed_mps": max_speed},
            )

        return PolicyRecommendation(
            decision_type=DecisionType.KEEP_CURRENT_ROUTE,
            priority=100,
            confidence=1.0,
            explanation="No safety constraints violated. Route is clear.",
            policy_name=self.name,
            veto=False,
        )
