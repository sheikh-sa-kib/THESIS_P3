"""CommunicationPolicy — decide when to broadcast new information."""

from __future__ import annotations

from e3hybrid.communication.enums import MessageType
from e3hybrid.decision.config import DecisionConfig
from e3hybrid.decision.observation import VehicleObservation
from e3hybrid.decision.policy import PolicyRecommendation
from e3hybrid.decision.types import DecisionType
from e3hybrid.emergency.enums import EmergencyEventType


class CommunicationPolicy:
    """Decide when the vehicle should broadcast new information — priority 50."""

    name: str = "communication"

    def __init__(self, config: DecisionConfig) -> None:
        self._config = config

    @property
    def enabled(self) -> bool:
        return self._config.communication.enabled

    def evaluate(self, observation: VehicleObservation) -> PolicyRecommendation:
        """Check for new events worth broadcasting."""

        cfg = self._config.communication
        snap = observation.graph_snapshot

        # New road closure visible in neighbourhood → broadcast.
        if cfg.broadcast_new_closures and snap.blocked_edge_ids:
            blocked_list = [str(e) for e in sorted(snap.blocked_edge_ids)]
            return PolicyRecommendation(
                decision_type=DecisionType.BROADCAST_MESSAGE,
                priority=50,
                confidence=0.9,
                explanation=(
                    f"Blocked edges detected in neighbourhood: "
                    f"{blocked_list[:3]}. Broadcasting road closure alert."
                ),
                policy_name=self.name,
                veto=False,
                payload={
                    "message_type": str(MessageType.ROAD_CLOSURE),
                    "blocked_edge_ids": blocked_list,
                },
            )

        # New hazard in neighbourhood → broadcast.
        if cfg.broadcast_hazards and snap.current_edge is not None:
            edge = snap.current_edge
            if edge.hazard_penalty_s > 0:
                return PolicyRecommendation(
                    decision_type=DecisionType.BROADCAST_MESSAGE,
                    priority=50,
                    confidence=0.8,
                    explanation=(
                        f"Hazard detected on edge '{edge.edge_id}' "
                        f"(penalty={edge.hazard_penalty_s:.1f} s). "
                        f"Broadcasting hazard alert."
                    ),
                    policy_name=self.name,
                    veto=False,
                    payload={
                        "message_type": str(MessageType.HAZARD),
                        "edge_id": str(edge.edge_id),
                        "hazard_penalty_s": edge.hazard_penalty_s,
                    },
                )

        return PolicyRecommendation(
            decision_type=DecisionType.KEEP_CURRENT_ROUTE,
            priority=50,
            confidence=1.0,
            explanation="No new information worth broadcasting.",
            policy_name=self.name,
            veto=False,
        )
