"""Policy registration — registers all policies with the global registry.

This module should be imported once at application startup to register all
available policies with the global PolicyRegistry.
"""

from __future__ import annotations

from e3hybrid.decision.config import DecisionConfig
from e3hybrid.decision.policy_registry import register_policy

# Import all policy implementations.
from e3hybrid.decision.policies.battery import BatteryPolicy
from e3hybrid.decision.policies.communication import CommunicationPolicy
from e3hybrid.decision.policies.congestion import CongestionPolicy
from e3hybrid.decision.policies.emergency import EmergencyPolicy
from e3hybrid.decision.policies.routing_candidate import RoutingCandidatePolicy
from e3hybrid.decision.policies.safety import SafetyPolicy


def register_all_policies() -> None:
    """Register all Phase 6 policies with the global registry."""
    register_policy("safety", lambda cfg: SafetyPolicy(cfg))
    register_policy("emergency", lambda cfg: EmergencyPolicy(cfg))
    register_policy("battery", lambda cfg: BatteryPolicy(cfg))
    register_policy("communication", lambda cfg: CommunicationPolicy(cfg))
    register_policy("congestion", lambda cfg: CongestionPolicy(cfg))
    register_policy("routing_candidate", lambda cfg: RoutingCandidatePolicy(cfg))


# Auto-register on module import.
register_all_policies()
