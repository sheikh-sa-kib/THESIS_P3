"""Edge models for the internal road-network graph.

Design contract
---------------
``Edge`` holds only **immutable structural attributes** that describe the
physical road segment.  These fields never change after construction:

  edge_id, source, target, length_m, speed_limit_mps, lane_count, geometry

``MutableEdgeState`` holds **simulation-mutable attributes** that represent the
real-time condition of the segment during a run.  The ``Edge`` object is never
mutated; a new ``Edge`` is created via ``Edge.with_state(new_state)``.

This separation enforces the invariant that immutable road topology cannot be
silently overwritten by simulation state updates.

Mutable fields and their roles
-------------------------------
- ``is_blocked``             – Road is physically impassable (accident, closure).
- ``current_speed_mps``      – Measured or simulated flow speed.  ``None`` means
                               the speed limit is used as the effective speed.
- ``travel_time_override_s`` – Direct travel-time override bypassing length/speed
                               computation (e.g., SUMO-reported times).
- ``congestion_factor``      – Multiplicative slow-down from traffic density.
                               1.0 = free flow.  > 1.0 = congested.
- ``hazard_penalty_s``       – Additive time penalty for road hazard events.
- ``emergency_penalty_s``    – Additive time penalty for emergency corridor
                               restrictions.
- ``communication_penalty_s``– Additive time penalty for communication-disrupted
                               zones (used by hybrid cost providers).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from e3hybrid.core.exceptions import NetworkError
from e3hybrid.network.types import EdgeId, NodeId


# ---------------------------------------------------------------------------
# Mutable edge state
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MutableEdgeState:
    """Simulation-time state for a road-segment edge.

    All attributes here can be updated during a simulation run by replacing
    this object.  The parent ``Edge`` is never modified; callers use
    ``Edge.with_state(new_state)`` to produce an updated copy.
    """

    is_blocked: bool = False
    current_speed_mps: float | None = None
    travel_time_override_s: float | None = None
    congestion_factor: float = 1.0
    hazard_penalty_s: float = 0.0
    emergency_penalty_s: float = 0.0
    communication_penalty_s: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate mutable state fields and freeze metadata."""

        if self.current_speed_mps is not None and self.current_speed_mps <= 0:
            raise NetworkError("current_speed_mps must be positive when provided")
        if (
            self.travel_time_override_s is not None
            and self.travel_time_override_s <= 0
        ):
            raise NetworkError("travel_time_override_s must be positive when provided")
        if self.congestion_factor <= 0:
            raise NetworkError("congestion_factor must be positive")
        if self.hazard_penalty_s < 0:
            raise NetworkError("hazard_penalty_s must be non-negative")
        if self.emergency_penalty_s < 0:
            raise NetworkError("emergency_penalty_s must be non-negative")
        if self.communication_penalty_s < 0:
            raise NetworkError("communication_penalty_s must be non-negative")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        """Serialize mutable state to a JSON-compatible dictionary."""

        return {
            "is_blocked": self.is_blocked,
            "current_speed_mps": self.current_speed_mps,
            "travel_time_override_s": self.travel_time_override_s,
            "congestion_factor": self.congestion_factor,
            "hazard_penalty_s": self.hazard_penalty_s,
            "emergency_penalty_s": self.emergency_penalty_s,
            "communication_penalty_s": self.communication_penalty_s,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MutableEdgeState":
        """Create mutable state from a serialized dictionary."""

        return cls(
            is_blocked=_bool_value(data.get("is_blocked", False), "edge.is_blocked"),
            current_speed_mps=_optional_positive_float(
                data.get("current_speed_mps"), "edge.current_speed_mps"
            ),
            travel_time_override_s=_optional_positive_float(
                data.get("travel_time_override_s"), "edge.travel_time_override_s"
            ),
            congestion_factor=_positive_float(
                data.get("congestion_factor", 1.0), "edge.congestion_factor"
            ),
            hazard_penalty_s=_non_negative_float(
                data.get("hazard_penalty_s", 0.0), "edge.hazard_penalty_s"
            ),
            emergency_penalty_s=_non_negative_float(
                data.get("emergency_penalty_s", 0.0), "edge.emergency_penalty_s"
            ),
            communication_penalty_s=_non_negative_float(
                data.get("communication_penalty_s", 0.0),
                "edge.communication_penalty_s",
            ),
            metadata=_metadata_mapping(data.get("metadata")),
        )


# ---------------------------------------------------------------------------
# Backward-compatible alias
# ---------------------------------------------------------------------------

#: ``EdgeDynamicAttributes`` is retained as a public alias so that existing
#: callers and tests do not break while migrating to ``MutableEdgeState``.
EdgeDynamicAttributes = MutableEdgeState


# ---------------------------------------------------------------------------
# Immutable edge
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Edge:
    """A directed edge representing a traversable road segment.

    Immutable structural fields
    ---------------------------
    ``edge_id``        – Unique identifier within the graph.
    ``source``         – Identifier of the origin node.
    ``target``         – Identifier of the destination node.
    ``length_m``       – Physical length of the road segment in metres.
    ``speed_limit_mps``– Legal speed limit in metres per second.
    ``lane_count``     – Number of lanes (≥ 1).
    ``metadata``       – Arbitrary read-only annotations (tags, road class, …).

    The ``state`` field carries all simulation-mutable values and is the only
    field that changes between simulation ticks.
    """

    edge_id: EdgeId
    source: NodeId
    target: NodeId
    length_m: float
    speed_limit_mps: float
    lane_count: int = 1
    state: MutableEdgeState = field(default_factory=MutableEdgeState)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate immutable edge attributes and freeze metadata."""

        if not str(self.edge_id).strip():
            raise NetworkError("edge_id must be non-empty")
        if not str(self.source).strip():
            raise NetworkError("edge source must be non-empty")
        if not str(self.target).strip():
            raise NetworkError("edge target must be non-empty")
        if self.length_m <= 0:
            raise NetworkError("length_m must be positive")
        if self.speed_limit_mps <= 0:
            raise NetworkError("speed_limit_mps must be positive")
        if self.lane_count <= 0:
            raise NetworkError("lane_count must be positive")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    # ------------------------------------------------------------------
    # Convenience property
    # ------------------------------------------------------------------

    @property
    def effective_speed_mps(self) -> float:
        """Return the currently effective speed in metres per second.

        Uses ``state.current_speed_mps`` when present; falls back to the
        immutable ``speed_limit_mps``.
        """

        return self.state.current_speed_mps or self.speed_limit_mps

    # Backward-compatible property so callers using `.dynamic` still work.
    @property
    def dynamic(self) -> MutableEdgeState:
        """Backward-compatible alias for ``state``."""

        return self.state

    # ------------------------------------------------------------------
    # State update (immutable copy pattern)
    # ------------------------------------------------------------------

    def with_state(self, state: MutableEdgeState) -> "Edge":
        """Return a copy of this edge with updated mutable state.

        The immutable structural fields (edge_id, source, target, length_m,
        speed_limit_mps, lane_count, metadata) are never modified.
        """

        return Edge(
            edge_id=self.edge_id,
            source=self.source,
            target=self.target,
            length_m=self.length_m,
            speed_limit_mps=self.speed_limit_mps,
            lane_count=self.lane_count,
            state=state,
            metadata=self.metadata,
        )

    # Backward-compatible alias so existing callers still work.
    def with_dynamic_attributes(self, dynamic: MutableEdgeState) -> "Edge":
        """Backward-compatible alias for ``with_state``."""

        return self.with_state(dynamic)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the edge to a JSON-compatible dictionary."""

        return {
            "edge_id": str(self.edge_id),
            "source": str(self.source),
            "target": str(self.target),
            "length_m": self.length_m,
            "speed_limit_mps": self.speed_limit_mps,
            "lane_count": self.lane_count,
            "state": self.state.to_dict(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Edge":
        """Create an edge from a serialized dictionary."""

        required_fields = (
            "edge_id",
            "source",
            "target",
            "length_m",
            "speed_limit_mps",
        )
        missing_fields = [
            field_name for field_name in required_fields if field_name not in data
        ]
        if missing_fields:
            joined = ", ".join(missing_fields)
            raise NetworkError(f"serialized edge is missing field(s): {joined}")

        # Accept both old key name ("dynamic") and new key name ("state") so
        # previously serialized graphs can still be loaded.
        state_data = data.get("state") or data.get("dynamic") or {}
        if not isinstance(state_data, Mapping):
            raise NetworkError("edge.state must be a mapping")
        return cls(
            edge_id=EdgeId(str(data["edge_id"])),
            source=NodeId(str(data["source"])),
            target=NodeId(str(data["target"])),
            length_m=_positive_float(data["length_m"], "edge.length_m"),
            speed_limit_mps=_positive_float(
                data["speed_limit_mps"], "edge.speed_limit_mps"
            ),
            lane_count=_positive_int(data.get("lane_count", 1), "edge.lane_count"),
            state=MutableEdgeState.from_dict(state_data),
            metadata=_metadata_mapping(data.get("metadata")),
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _positive_float(value: Any, field_name: str) -> float:
    """Return a positive numeric value as a float."""

    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise NetworkError(f"{field_name} must be positive")
    return float(value)


def _non_negative_float(value: Any, field_name: str) -> float:
    """Return a non-negative numeric value as a float."""

    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        raise NetworkError(f"{field_name} must be non-negative")
    return float(value)


def _optional_positive_float(value: Any, field_name: str) -> float | None:
    """Return an optional positive numeric value as a float."""

    if value is None:
        return None
    return _positive_float(value, field_name)


def _positive_int(value: Any, field_name: str) -> int:
    """Return a positive integer value."""

    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise NetworkError(f"{field_name} must be a positive integer")
    return value


def _bool_value(value: Any, field_name: str) -> bool:
    """Return a boolean value."""

    if not isinstance(value, bool):
        raise NetworkError(f"{field_name} must be a boolean")
    return value


def _metadata_mapping(value: Any) -> Mapping[str, Any]:
    """Return metadata as a mapping or raise a network error."""

    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise NetworkError("metadata must be a mapping")
    return value
