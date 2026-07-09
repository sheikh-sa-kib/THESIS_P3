"""CompositeCostCalculator — computes weighted cost components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from e3hybrid.network.graph import Edge


@dataclass(frozen=True, slots=True)
class CostWeights:
    """Configurable weights for cost components.
    
    Attributes
    ----------
    distance:
        Weight for distance cost.
    time:
        Weight for travel time cost.
    energy:
        Weight for energy cost.
    congestion:
        Weight for congestion penalty.
    hazard:
        Weight for hazard penalty.
    emergency:
        Weight for emergency penalty.
    communication:
        Weight for communication penalty.
    """

    distance: float = 1.0
    time: float = 1.0
    energy: float = 1.0
    congestion: float = 1.0
    hazard: float = 1.0
    emergency: float = 1.0
    communication: float = 1.0

    def __post_init__(self) -> None:
        """Validate weights are non-negative."""
        if self.distance < 0:
            raise ValueError("distance weight must be non-negative")
        if self.time < 0:
            raise ValueError("time weight must be non-negative")
        if self.energy < 0:
            raise ValueError("energy weight must be non-negative")
        if self.congestion < 0:
            raise ValueError("congestion weight must be non-negative")
        if self.hazard < 0:
            raise ValueError("hazard weight must be non-negative")
        if self.emergency < 0:
            raise ValueError("emergency weight must be non-negative")
        if self.communication < 0:
            raise ValueError("communication weight must be non-negative")


@dataclass(frozen=True, slots=True)
class EdgeCostBreakdown:
    """Cost breakdown for a single edge.
    
    Attributes
    ----------
    distance_cost:
        Cost from physical distance.
    time_cost:
        Cost from travel time.
    energy_cost:
        Cost from energy consumption.
    congestion_penalty:
        Penalty from congestion factor.
    hazard_penalty:
        Penalty from hazard zones.
    emergency_penalty:
        Penalty from emergency corridors.
    communication_penalty:
        Penalty from communication disruption.
    """

    distance_cost: float
    time_cost: float
    energy_cost: float
    congestion_penalty: float
    hazard_penalty: float
    emergency_penalty: float
    communication_penalty: float


class CompositeCostCalculator:
    """Computes weighted cost components for edges.
    
    Design Decision (DD-030)
    -----------------------
    Modular cost architecture with independently configurable components
    allows different objective functions without modifying algorithms.
    """

    def __init__(self, weights: CostWeights = CostWeights()) -> None:
        """Initialize the cost calculator.
        
        Parameters
        ----------
        weights:
            Configurable weights for each cost component.
        """
        self._weights = weights

    def compute_edge_cost(self, edge: "Edge") -> tuple[float, EdgeCostBreakdown]:
        """Compute the total cost for traversing an edge.
        
        Parameters
        ----------
        edge:
            The edge to compute cost for.
        
        Returns
        -------
        tuple[float, EdgeCostBreakdown]
            Total cost and detailed cost breakdown.
        """
        # Extract edge properties
        length_m = edge.length_m
        speed_limit_mps = edge.speed_limit_mps
        
        # Compute base travel time
        if edge.state.current_speed_mps is not None:
            effective_speed = edge.state.current_speed_mps
        else:
            effective_speed = speed_limit_mps
        
        if effective_speed > 0:
            base_time_s = length_m / effective_speed
        else:
            base_time_s = float("inf")
        
        # Apply congestion factor
        congested_time_s = base_time_s * edge.state.congestion_factor
        
        # Compute individual cost components
        distance_cost = length_m
        time_cost = congested_time_s
        energy_cost = 0.0  # Will be computed by energy model in future phases
        
        # Penalties
        congestion_penalty = (congested_time_s - base_time_s) if base_time_s != float("inf") else 0.0
        hazard_penalty = edge.state.hazard_penalty_s
        emergency_penalty = edge.state.emergency_penalty_s
        communication_penalty = edge.state.communication_penalty_s
        
        breakdown = EdgeCostBreakdown(
            distance_cost=distance_cost,
            time_cost=time_cost,
            energy_cost=energy_cost,
            congestion_penalty=congestion_penalty,
            hazard_penalty=hazard_penalty,
            emergency_penalty=emergency_penalty,
            communication_penalty=communication_penalty,
        )
        
        # Apply weights
        total_cost = (
            self._weights.distance * distance_cost
            + self._weights.time * time_cost
            + self._weights.energy * energy_cost
            + self._weights.congestion * congestion_penalty
            + self._weights.hazard * hazard_penalty
            + self._weights.emergency * emergency_penalty
            + self._weights.communication * communication_penalty
        )
        
        return total_cost, breakdown

    def compute_route_cost(
        self,
        edges: list["Edge"],
    ) -> tuple[float, EdgeCostBreakdown]:
        """Compute the total cost for a sequence of edges.
        
        Parameters
        ----------
        edges:
            Ordered list of edges in the route.
        
        Returns
        -------
        tuple[float, EdgeCostBreakdown]
            Total cost and aggregated cost breakdown.
        """
        total_distance_cost = 0.0
        total_time_cost = 0.0
        total_energy_cost = 0.0
        total_congestion_penalty = 0.0
        total_hazard_penalty = 0.0
        total_emergency_penalty = 0.0
        total_communication_penalty = 0.0
        
        for edge in edges:
            _, breakdown = self.compute_edge_cost(edge)
            total_distance_cost += breakdown.distance_cost
            total_time_cost += breakdown.time_cost
            total_energy_cost += breakdown.energy_cost
            total_congestion_penalty += breakdown.congestion_penalty
            total_hazard_penalty += breakdown.hazard_penalty
            total_emergency_penalty += breakdown.emergency_penalty
            total_communication_penalty += breakdown.communication_penalty
        
        # Apply weights
        total_cost = (
            self._weights.distance * total_distance_cost
            + self._weights.time * total_time_cost
            + self._weights.energy * total_energy_cost
            + self._weights.congestion * total_congestion_penalty
            + self._weights.hazard * total_hazard_penalty
            + self._weights.emergency * total_emergency_penalty
            + self._weights.communication * total_communication_penalty
        )
        
        aggregated_breakdown = EdgeCostBreakdown(
            distance_cost=total_distance_cost,
            time_cost=total_time_cost,
            energy_cost=total_energy_cost,
            congestion_penalty=total_congestion_penalty,
            hazard_penalty=total_hazard_penalty,
            emergency_penalty=total_emergency_penalty,
            communication_penalty=total_communication_penalty,
        )
        
        return total_cost, aggregated_breakdown
