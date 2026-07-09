"""EmergencyPolicy — react to active emergency events.

Veto conditions:
- EmergencyVehicleEvent with priority >= min_priority_value → YIELD (veto)

Non-veto conditions:
- Road closure or hazard event detected in neighbourhood → REQUEST_REROUTE

Decision 4 (approved): EmergencyVehicleEvent only publishes a corridor request.
This policy reads the event and produces a YIELD recommendation.  It does NOT
compute routes or corridors.
"""

from __future__ import annotations

from e3hybrid.communication.enums import Priority
from e3hybrid.decision.config import DecisionConfig
from e3hybrid.decision.observation import VehicleObservation
from e3hybrid.decision.policy import PolicyRecommendation
from e3hybrid.decision.types import DecisionType
from e3hybrid.emergency.enums import EmergencyEventType


class EmergencyPolicy:
    """React to active emergency events — priority 90."""

    name: str = "emergency"

    def __init__(self, config: DecisionConfig) -> None:
        self._config = config

    @property
    def enabled(self) -> bool:
        return self._config.emergency.enabled

    def evaluate(self, observation: VehicleObservation) -> PolicyRecommendation:
        """Scan active events and inbox for emergency signals."""

        cfg = self._config.emergency

        # Check active emergency vehicle events — hard yield constraint.
        for event in observation.active_events:
            if (
                event.event_type == EmergencyEventType.EMERGENCY_VEHICLE
                and int(event.priority) >= cfg.min_priority_value
                and event.is_active(observation.sim_time_s)
            ):
                return PolicyRecommendation(
                    decision_type=DecisionType.YIELD,
                    priority=90,
                    confidence=1.0,
                    explanation=(
                        f"EmergencyVehicleEvent '{event.event_id}' is active "
                        f"(priority={event.priority.name}). "
                        f"Yielding for {cfg.yield_duration_s:.0f} s."
                    ),
                    policy_name=self.name,
                    veto=True,
                    payload={
                        "emergency_event_id": str(event.event_id),
                        "wait_duration_s": cfg.yield_duration_s,
                    },
                )

        # Check for active road closures in neighbourhood.
        for event in observation.active_events:
            if (
                event.event_type in (
                    EmergencyEventType.ROAD_CLOSURE,
                    EmergencyEventType.TRAFFIC_ACCIDENT,
                )
                and event.is_active(observation.sim_time_s)
            ):
                affected = event.affected_edge_ids
                snapshot_blocked = {
                    eid for eid in affected
                    if observation.graph_snapshot.is_blocked(eid)
                }
                if snapshot_blocked:
                    # Safety policy will veto — this is a soft reinforcement.
                    return PolicyRecommendation(
                        decision_type=DecisionType.REQUEST_REROUTE,
                        priority=85,
                        confidence=0.9,
                        explanation=(
                            f"Emergency event '{event.event_id}' "
                            f"({event.event_type}) blocks edges in neighbourhood. "
                            f"Requesting reroute."
                        ),
                        policy_name=self.name,
                        veto=False,
                    )

        return PolicyRecommendation(
            decision_type=DecisionType.KEEP_CURRENT_ROUTE,
            priority=90,
            confidence=1.0,
            explanation="No active emergency events require action.",
            policy_name=self.name,
            veto=False,
        )
