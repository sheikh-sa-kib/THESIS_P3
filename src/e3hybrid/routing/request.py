"""RoutingRequest — immutable routing request from Decision Engine or simulation core."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from e3hybrid.network.types import NodeId
from e3hybrid.vehicle.types import VehicleId


@dataclass(frozen=True, slots=True)
class RoutingRequest:
    """Immutable routing request.
    
    All parameters are validated at construction time.
    
    Attributes
    ----------
    source_node:
        Origin node ID (must exist in graph).
    destination_node:
        Target node ID (must exist in graph).
    vehicle_id:
        Vehicle identifier (for logging and cache key).
    vehicle_constraints:
        Operational limits (min/max SoC, max speed, max payload).
    battery_state:
        Current battery snapshot (soc_kwh, capacity_kwh, soc_fraction).
    max_candidates:
        Maximum number of candidates to return.
    timeout_s:
        Maximum allowed runtime before aborting.
    metadata:
        Optional algorithm-specific parameters (e.g., ACO alpha, beta, rho).
    """

    source_node: NodeId
    destination_node: NodeId
    vehicle_id: VehicleId
    vehicle_constraints: Any  # VehicleConstraints protocol
    battery_state: Any  # BatterySnapshot protocol
    max_candidates: int
    timeout_s: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate request parameters."""
        if self.max_candidates <= 0:
            raise ValueError("max_candidates must be positive")
        if self.timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        if self.source_node == self.destination_node:
            raise ValueError("source_node and destination_node must be different")
