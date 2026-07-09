"""RouteCost — immutable cost breakdown for a route."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RouteCost:
    """Immutable cost breakdown for a route.
    
    Provides transparency into how total cost was computed.
    
    Attributes
    ----------
    total:
        Total scalar cost.
    distance_cost:
        Cost component from physical distance.
    time_cost:
        Cost component from travel time.
    energy_cost:
        Cost component from energy consumption.
    congestion_penalty:
        Penalty from congestion factor.
    hazard_penalty:
        Penalty from hazard zones.
    emergency_penalty:
        Penalty from emergency corridors.
    communication_penalty:
        Penalty from communication disruption.
    components:
        Dictionary of all cost components for analysis.
    """

    total: float
    distance_cost: float
    time_cost: float
    energy_cost: float
    congestion_penalty: float
    hazard_penalty: float
    emergency_penalty: float
    communication_penalty: float
    components: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate cost consistency."""
        if self.total < 0:
            raise ValueError("total must be non-negative")
        if self.distance_cost < 0:
            raise ValueError("distance_cost must be non-negative")
        if self.time_cost < 0:
            raise ValueError("time_cost must be non-negative")
        if self.energy_cost < 0:
            raise ValueError("energy_cost must be non-negative")
        if self.congestion_penalty < 0:
            raise ValueError("congestion_penalty must be non-negative")
        if self.hazard_penalty < 0:
            raise ValueError("hazard_penalty must be non-negative")
        if self.emergency_penalty < 0:
            raise ValueError("emergency_penalty must be non-negative")
        if self.communication_penalty < 0:
            raise ValueError("communication_penalty must be non-negative")

        # Verify total matches sum of components (within floating-point tolerance)
        computed_total = (
            self.distance_cost
            + self.time_cost
            + self.energy_cost
            + self.congestion_penalty
            + self.hazard_penalty
            + self.emergency_penalty
            + self.communication_penalty
        )
        if abs(self.total - computed_total) > 1e-6:
            raise ValueError(
                f"total ({self.total}) does not match sum of components ({computed_total})"
            )
