"""DecisionPolicy Protocol and PolicyRecommendation dataclass.

Every policy is INDEPENDENT.  Policies never call each other.
Every policy returns a PolicyRecommendation.  The DecisionAggregationPolicy
selects the winning recommendation.

Hard constraints are expressed via ``veto=True``.  A vetoing recommendation
is adopted immediately — no lower-priority recommendation can override it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from e3hybrid.decision.types import DecisionType


@dataclass(frozen=True, slots=True)
class PolicyRecommendation:
    """A single policy's recommendation for what a vehicle should do.

    Attributes
    ----------
    decision_type:
        The recommended action.
    priority:
        Higher integer = more urgent.  Resolved by DecisionAggregationPolicy.
        Range is [0, 100]; 0 = lowest, 100 = highest.
    confidence:
        How confident the policy is in this recommendation.  [0.0, 1.0].
        Used as tiebreaker when two recommendations have equal priority.
    explanation:
        Human-readable justification for thesis debugging and decision logs.
        MANDATORY — empty string is rejected by DecisionEngine.
    veto:
        When True this is a HARD CONSTRAINT.  The aggregation policy must
        adopt this recommendation regardless of all others.
        Only one policy should veto per evaluation cycle; if multiple veto,
        the highest-priority veto wins.
    payload:
        Type-specific parameters for the simulation core.  None for simple
        decisions (e.g., KEEP_CURRENT_ROUTE).
    policy_name:
        Name of the policy that produced this recommendation.  Used in the
        Decision.applied_policies field and decision_log.csv.
    """

    decision_type: DecisionType
    priority: int
    confidence: float
    explanation: str
    policy_name: str
    veto: bool = False
    payload: Any = None

    def __post_init__(self) -> None:
        from e3hybrid.core.exceptions import DecisionError
        if not (0 <= self.priority <= 100):
            raise DecisionError("priority must be in [0, 100]")
        if not (0.0 <= self.confidence <= 1.0):
            raise DecisionError("confidence must be in [0.0, 1.0]")
        if not self.explanation.strip():
            raise DecisionError(
                f"explanation is mandatory and must be non-empty "
                f"(policy: {self.policy_name})"
            )
        if not self.policy_name.strip():
            raise DecisionError("policy_name must be non-empty")


class DecisionPolicy(Protocol):
    """Interface that every policy must satisfy.

    Policies are independent.  They receive the full VehicleObservation and
    return exactly one PolicyRecommendation.  They never call other policies,
    never modify the graph, never send messages, and never call routing
    algorithms.
    """

    @property
    def name(self) -> str:
        """Return the stable policy name used in logs."""
        ...

    @property
    def enabled(self) -> bool:
        """Return True when this policy should participate in evaluation."""
        ...

    def evaluate(
        self, observation: "VehicleObservation"  # type: ignore[name-defined]
    ) -> PolicyRecommendation:
        """Evaluate the observation and return a recommendation.

        Must never raise.  Return a KEEP_CURRENT_ROUTE recommendation with
        low confidence when the policy has no opinion.
        """
        ...
