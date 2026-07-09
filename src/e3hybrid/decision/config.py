"""DecisionConfig — all policy thresholds loaded from YAML.

Nothing is hardcoded.  Every threshold used by every policy comes from
this configuration object.

Example YAML section (see docs/decision_engine_design.md §10):

    decision_engine:
      max_candidates: 3
      neighbourhood_depth: 2
      safety_policy:
        enabled: true
      emergency_policy:
        enabled: true
        yield_duration_s: 30.0
        min_priority: critical
      battery_policy:
        enabled: true
        emergency_stop_threshold_fraction: 0.0
        wait_threshold_fraction: 0.10
        conservation_threshold_fraction: 0.20
      congestion_policy:
        enabled: true
        reroute_congestion_threshold: 2.5
        reroute_hazard_threshold_s: 60.0
      communication_policy:
        enabled: true
        broadcast_new_closures: true
        broadcast_hazards: true
        stale_message_age_s: 30.0
      routing_candidate_policy:
        enabled: true
        improvement_threshold: 0.05
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class SafetyPolicyConfig:
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class EmergencyPolicyConfig:
    enabled: bool = True
    yield_duration_s: float = 30.0
    min_priority_value: int = 4     # Priority.CRITICAL = 4


@dataclass(frozen=True, slots=True)
class BatteryPolicyConfig:
    enabled: bool = True
    emergency_stop_threshold_fraction: float = 0.0
    wait_threshold_fraction: float = 0.10
    conservation_threshold_fraction: float = 0.20


@dataclass(frozen=True, slots=True)
class CongestionPolicyConfig:
    enabled: bool = True
    reroute_congestion_threshold: float = 2.5
    reroute_hazard_threshold_s: float = 60.0


@dataclass(frozen=True, slots=True)
class CommunicationPolicyConfig:
    enabled: bool = True
    broadcast_new_closures: bool = True
    broadcast_hazards: bool = True
    stale_message_age_s: float = 30.0


@dataclass(frozen=True, slots=True)
class RoutingCandidatePolicyConfig:
    enabled: bool = True
    improvement_threshold: float = 0.05


@dataclass(frozen=True, slots=True)
class DecisionConfig:
    """Complete Decision Engine configuration.

    Attributes
    ----------
    max_candidates:
        Maximum number of routing candidates to request per evaluation.
    neighbourhood_depth:
        Number of hops from the current edge to include in GraphSnapshot.
    safety:   SafetyPolicyConfig
    emergency:EmergencyPolicyConfig
    battery:  BatteryPolicyConfig
    congestion:CongestionPolicyConfig
    communication:CommunicationPolicyConfig
    routing:  RoutingCandidatePolicyConfig
    """

    max_candidates: int = 3
    neighbourhood_depth: int = 2
    safety: SafetyPolicyConfig = field(default_factory=SafetyPolicyConfig)
    emergency: EmergencyPolicyConfig = field(default_factory=EmergencyPolicyConfig)
    battery: BatteryPolicyConfig = field(default_factory=BatteryPolicyConfig)
    congestion: CongestionPolicyConfig = field(default_factory=CongestionPolicyConfig)
    communication: CommunicationPolicyConfig = field(
        default_factory=CommunicationPolicyConfig
    )
    routing: RoutingCandidatePolicyConfig = field(
        default_factory=RoutingCandidatePolicyConfig
    )

    @classmethod
    def default(cls) -> "DecisionConfig":
        """Return default configuration suitable for Phase 6 testing."""
        return cls()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DecisionConfig":
        """Build from the ``decision_engine`` section of a YAML config."""

        de = data.get("decision_engine", {})

        def _sub(key: str) -> Mapping[str, Any]:
            return de.get(key, {})

        s = _sub("safety_policy")
        e = _sub("emergency_policy")
        b = _sub("battery_policy")
        cg = _sub("congestion_policy")
        cm = _sub("communication_policy")
        r = _sub("routing_candidate_policy")

        return cls(
            max_candidates=int(de.get("max_candidates", 3)),
            neighbourhood_depth=int(de.get("neighbourhood_depth", 2)),
            safety=SafetyPolicyConfig(
                enabled=bool(s.get("enabled", True)),
            ),
            emergency=EmergencyPolicyConfig(
                enabled=bool(e.get("enabled", True)),
                yield_duration_s=float(e.get("yield_duration_s", 30.0)),
                min_priority_value=int(e.get("min_priority_value", 4)),
            ),
            battery=BatteryPolicyConfig(
                enabled=bool(b.get("enabled", True)),
                emergency_stop_threshold_fraction=float(
                    b.get("emergency_stop_threshold_fraction", 0.0)
                ),
                wait_threshold_fraction=float(
                    b.get("wait_threshold_fraction", 0.10)
                ),
                conservation_threshold_fraction=float(
                    b.get("conservation_threshold_fraction", 0.20)
                ),
            ),
            congestion=CongestionPolicyConfig(
                enabled=bool(cg.get("enabled", True)),
                reroute_congestion_threshold=float(
                    cg.get("reroute_congestion_threshold", 2.5)
                ),
                reroute_hazard_threshold_s=float(
                    cg.get("reroute_hazard_threshold_s", 60.0)
                ),
            ),
            communication=CommunicationPolicyConfig(
                enabled=bool(cm.get("enabled", True)),
                broadcast_new_closures=bool(cm.get("broadcast_new_closures", True)),
                broadcast_hazards=bool(cm.get("broadcast_hazards", True)),
                stale_message_age_s=float(cm.get("stale_message_age_s", 30.0)),
            ),
            routing=RoutingCandidatePolicyConfig(
                enabled=bool(r.get("enabled", True)),
                improvement_threshold=float(r.get("improvement_threshold", 0.05)),
            ),
        )
