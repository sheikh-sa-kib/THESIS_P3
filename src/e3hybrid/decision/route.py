"""RouteCandidate, RouteCandidateSource Protocol, NullRouteCandidateSource.

Design (Decision 3 — approved)
-------------------------------
Candidate routes are NEVER pre-filtered before the Decision Engine sees them.
Every routing algorithm submits its complete candidate set.  The
RoutingCandidatePolicy evaluates them on objective values only.

The Decision Engine NEVER knows which algorithm produced a candidate.  The
``algorithm`` field exists only for logging, evaluation, and research analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from e3hybrid.decision.types import RouteId
from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.vehicle.types import VehicleId


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    """A single candidate route produced by a RouteCandidateSource.

    Attributes
    ----------
    route_id:
        Unique identifier within one evaluation cycle.
    node_sequence:
        Ordered tuple of NodeIds from origin to destination.
    edge_sequence:
        Ordered tuple of EdgeIds corresponding to each traversal step.
    total_cost:
        Scalar cost in the CostProvider's units.  The DE evaluates ONLY
        this value — it never inspects how cost was computed.
    algorithm:
        Name of the algorithm that produced this candidate.
        Used ONLY for logging and thesis metrics; never used in evaluation.
    metadata:
        Arbitrary annotations (pheromone level, particle score, …).
        Also for logging only.
    """

    route_id: RouteId
    node_sequence: tuple[NodeId, ...]
    edge_sequence: tuple[EdgeId, ...]
    total_cost: float
    algorithm: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        from e3hybrid.core.exceptions import DecisionError
        if not str(self.route_id).strip():
            raise DecisionError("route_id must be non-empty")
        if self.total_cost < 0:
            raise DecisionError("total_cost must be non-negative")
        if not self.node_sequence:
            raise DecisionError("node_sequence must not be empty")


class RouteCandidateSource(Protocol):
    """Interface through which the Decision Engine requests routing candidates.

    The DE is completely agnostic about whether the source is Dijkstra, A*,
    ACO, BCO, PSO, or E³-Hybrid.  The same interface serves all algorithms.
    """

    def get_candidates(
        self,
        vehicle_id: VehicleId,
        origin: NodeId,
        destination: NodeId,
        max_candidates: int,
    ) -> tuple[RouteCandidate, ...]:
        """Return up to ``max_candidates`` candidates, best-first by cost."""
        ...


class NullRouteCandidateSource:
    """Phase 6 placeholder — always returns an empty candidate tuple.

    Used until Phase 7 (Dijkstra) is injected.  The Decision Engine must
    handle an empty candidate tuple gracefully (falls back to KEEP_CURRENT_ROUTE).
    """

    def get_candidates(
        self,
        vehicle_id: VehicleId,
        origin: NodeId,
        destination: NodeId,
        max_candidates: int,
    ) -> tuple[RouteCandidate, ...]:
        """Return empty tuple unconditionally."""
        return ()
