"""CongestionPolicy — react to raised congestion and hazard penalties."""

from __future__ import annotations

from e3hybrid.decision.config import DecisionConfig
from e3hybrid.decision.observation import VehicleObservation
from e3hybrid.decision.policy import PolicyRecommendation
from e3hybrid.decision.types import DecisionType


class CongestionPolicy:
    """Non-blocking reroute suggestion for congestion and hazard — priority 60."""

    name: str = "congestion"

    def __init__(self, config: DecisionConfig) -> None:
        self._config = config

    @property
    def enabled(self) -> bool:
        return self._config.congestion.enabled

    def evaluate(self, observation: VehicleObservation) -> PolicyRecommendation:
        """Check current and neighbouring edges for congestion or hazard."""

        cfg = self._config.congestion
        snap = observation.graph_snapshot

        # Check current edge.
        if snap.current_edge is not None:
            edge = snap.current_edge
            if edge.congestion_factor >= cfg.reroute_congestion_threshold:
                return PolicyRecommendation(
                    decision_type=DecisionType.REQUEST_REROUTE,
                    priority=60,
                    confidence=0.75,
                    explanation=(
                        f"Current edge '{edge.edge_id}' has congestion_factor "
                        f"{edge.congestion_factor:.2f} >= threshold "
                        f"{cfg.reroute_congestion_threshold:.2f}. "
                        f"Requesting reroute."
                    ),
                    policy_name=self.name,
                    veto=False,
                )
            if edge.hazard_penalty_s >= cfg.reroute_hazard_threshold_s:
                return PolicyRecommendation(
                    decision_type=DecisionType.REQUEST_REROUTE,
                    priority=60,
                    confidence=0.70,
                    explanation=(
                        f"Current edge '{edge.edge_id}' has hazard_penalty_s "
                        f"{edge.hazard_penalty_s:.1f} s >= threshold "
                        f"{cfg.reroute_hazard_threshold_s:.1f} s. "
                        f"Requesting reroute."
                    ),
                    policy_name=self.name,
                    veto=False,
                )

        return PolicyRecommendation(
            decision_type=DecisionType.KEEP_CURRENT_ROUTE,
            priority=60,
            confidence=1.0,
            explanation="No significant congestion or hazard detected on current edge.",
            policy_name=self.name,
            veto=False,
        )
