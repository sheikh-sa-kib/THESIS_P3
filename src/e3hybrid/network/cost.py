"""Cost-provider interfaces and implementations for road-network edges.

Design contract
---------------
The graph itself does not decide routing costs.  Routing algorithms receive a
``CostProvider`` and call ``provider.cost(edge)`` — they never inspect edge
internals directly.  This decoupling allows future phases to swap in:

  - ``DistanceCostProvider``      – raw metre distance (baseline)
  - ``TravelTimeCostProvider``    – travel time in seconds (default)
  - energy-consumption providers  – to be added after literature model approval
  - emergency-aware providers     – combining travel time + emergency penalties
  - hybrid objective providers    – weighted multi-objective combinations

All implementations must satisfy the ``CostProvider`` Protocol so they can be
used interchangeably by any routing algorithm.

``EdgeCost`` structure
----------------------
  value        – primary scalar cost consumed by routing algorithms
  is_blocked   – True when the edge is impassable (cost = inf)
  components   – named breakdown of cost contributions for diagnostics

Routing algorithms must check ``is_blocked`` and skip the edge rather than
propagating ``inf`` values into path-weight accumulators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import inf
from typing import Protocol

from e3hybrid.network.edge import Edge


# ---------------------------------------------------------------------------
# Structured cost result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EdgeCost:
    """Structured cost result for traversing a single edge.

    Attributes
    ----------
    value:
        Scalar cost in the provider's units (seconds, metres, …).
        ``math.inf`` when ``is_blocked`` is True.
    is_blocked:
        True when the edge is physically impassable.  Routing algorithms must
        treat this as a hard constraint and not traverse the edge.
    components:
        Named breakdown of how ``value`` was computed.  Used for diagnostics,
        logging, and audit trails.  Not consumed by routing algorithms.
    """

    value: float
    is_blocked: bool = False
    components: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class CostProvider(Protocol):
    """Protocol that all edge-cost providers must satisfy.

    Routing algorithms depend only on this interface.  They must never import
    a concrete provider class directly; they receive one via dependency
    injection.
    """

    def cost(self, edge: Edge) -> EdgeCost:
        """Return a structured cost for traversing ``edge``.

        Implementations must:
        - Return ``EdgeCost(value=inf, is_blocked=True, ...)`` for blocked edges.
        - Never raise for edges that are valid according to the graph model.
        - Be deterministic given the same edge state.
        """


# ---------------------------------------------------------------------------
# Concrete providers
# ---------------------------------------------------------------------------


class DistanceCostProvider:
    """Edge cost = physical road-segment length in metres.

    This is the simplest possible baseline.  It ignores travel time, speed,
    congestion, and any penalties.  Blocked edges are still returned as inf.
    """

    def cost(self, edge: Edge) -> EdgeCost:
        """Return distance cost in metres for an edge."""

        if edge.state.is_blocked:
            return EdgeCost(value=inf, is_blocked=True, components={"blocked": 1.0})
        return EdgeCost(
            value=edge.length_m,
            is_blocked=False,
            components={"distance_m": edge.length_m},
        )


class TravelTimeCostProvider:
    """Edge cost = travel time in seconds.

    Computation
    -----------
    1. If the edge is blocked → cost = inf.
    2. Base time = ``state.travel_time_override_s`` if set, otherwise
       ``length_m / effective_speed_mps``.
    3. Congested time = base_time × ``state.congestion_factor``.
    4. Total = congested_time
               + ``state.hazard_penalty_s``
               + ``state.emergency_penalty_s``
               + ``state.communication_penalty_s``.

    Each additive term is included in ``components`` for diagnostics.
    """

    def cost(self, edge: Edge) -> EdgeCost:
        """Return travel-time cost in seconds for an edge."""

        if edge.state.is_blocked:
            return EdgeCost(value=inf, is_blocked=True, components={"blocked": 1.0})

        base_time = edge.state.travel_time_override_s
        if base_time is None:
            base_time = edge.length_m / edge.effective_speed_mps

        congested_time = base_time * edge.state.congestion_factor

        total = (
            congested_time
            + edge.state.hazard_penalty_s
            + edge.state.emergency_penalty_s
            + edge.state.communication_penalty_s
        )

        return EdgeCost(
            value=total,
            is_blocked=False,
            components={
                "base_travel_time_s": base_time,
                "congestion_factor": edge.state.congestion_factor,
                "congested_time_s": congested_time,
                "hazard_penalty_s": edge.state.hazard_penalty_s,
                "emergency_penalty_s": edge.state.emergency_penalty_s,
                "communication_penalty_s": edge.state.communication_penalty_s,
            },
        )
