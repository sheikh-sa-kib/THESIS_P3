"""Decision dataclass — the output of one Decision Engine evaluation cycle.

Every Decision is IMMUTABLE.
Every Decision MUST contain a non-empty explanation.
Every Decision is written immediately to the DecisionLog.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from e3hybrid.decision.policy import PolicyRecommendation
from e3hybrid.decision.types import DecisionId, DecisionType
from e3hybrid.vehicle.types import VehicleId


@dataclass(frozen=True, slots=True)
class Decision:
    """The output of one Decision Engine evaluation cycle for one vehicle.

    Attributes
    ----------
    decision_id:
        Unique identifier for this decision (UUID).
    vehicle_id:
        Vehicle for which this decision was produced.
    sim_time_s:
        Simulation clock at evaluation time (for deterministic replay).
    decision_type:
        The chosen action type.
    trigger:
        Short cause description (e.g., "road_closure_on_route",
        "battery_below_threshold", "no_new_information").
    explanation:
        Mandatory human-readable justification.  Used in decision_log.csv,
        debug output, and thesis evaluation screenshots.
    winning_policy:
        Name of the policy whose recommendation was selected.
    applied_policies:
        Names of ALL policies evaluated this cycle.
    veto:
        True when a hard constraint forced this decision.
    confidence:
        Confidence level from the winning policy [0.0, 1.0].
    payload:
        Type-specific parameters for the simulation core.
    all_recommendations:
        Complete list of every policy recommendation from this cycle.
        Stored for full auditability — never discarded.
    """

    decision_id: DecisionId
    vehicle_id: VehicleId
    sim_time_s: float
    decision_type: DecisionType
    trigger: str
    explanation: str
    winning_policy: str
    applied_policies: tuple[str, ...]
    veto: bool = False
    confidence: float = 1.0
    payload: Any = None
    all_recommendations: tuple[PolicyRecommendation, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        from e3hybrid.core.exceptions import DecisionError
        if not self.explanation.strip():
            raise DecisionError(
                f"Decision explanation is mandatory "
                f"(vehicle={self.vehicle_id}, type={self.decision_type})"
            )
        if not self.trigger.strip():
            raise DecisionError("Decision trigger must be non-empty")

    @classmethod
    def create(
        cls,
        vehicle_id: VehicleId,
        sim_time_s: float,
        decision_type: DecisionType,
        trigger: str,
        explanation: str,
        winning_policy: str,
        applied_policies: tuple[str, ...],
        recommendations: tuple[PolicyRecommendation, ...],
        veto: bool = False,
        confidence: float = 1.0,
        payload: Any = None,
    ) -> "Decision":
        """Factory — auto-generates a UUID decision_id."""
        return cls(
            decision_id=DecisionId(str(uuid.uuid4())),
            vehicle_id=vehicle_id,
            sim_time_s=sim_time_s,
            decision_type=decision_type,
            trigger=trigger,
            explanation=explanation,
            winning_policy=winning_policy,
            applied_policies=applied_policies,
            veto=veto,
            confidence=confidence,
            payload=payload,
            all_recommendations=recommendations,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON/CSV-compatible dictionary."""
        return {
            "decision_id":     str(self.decision_id),
            "vehicle_id":      str(self.vehicle_id),
            "sim_time_s":      self.sim_time_s,
            "decision_type":   str(self.decision_type),
            "trigger":         self.trigger,
            "explanation":     self.explanation,
            "winning_policy":  self.winning_policy,
            "applied_policies": ",".join(self.applied_policies),
            "veto":            self.veto,
            "confidence":      self.confidence,
        }

    def __repr__(self) -> str:
        return (
            f"Decision("
            f"type={self.decision_type}, "
            f"vehicle={self.vehicle_id}, "
            f"t={self.sim_time_s:.1f}s, "
            f"policy={self.winning_policy}, "
            f"veto={self.veto})"
        )
