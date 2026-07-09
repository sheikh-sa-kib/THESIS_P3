"""ElectricVehicle entity.

Design
------
The `ElectricVehicle` entity holds the vehicle's identity, constraints, and
current state. It does not know how energy is calculated. Energy consumption
is delegated entirely to the injected `EnergyModel`.

This follows the same philosophy as the graph's `CostProvider`:
- The vehicle entity never imports a concrete energy model.
- It receives any object satisfying the `EnergyModel` Protocol.
- Routing algorithms never touch the energy model directly; they call
  `vehicle.traverse_edge(edge, speed, accel, grade, duration)`.

Immutability contract
---------------------
`vehicle_id`, `constraints`, and `energy_model` are set at construction and
never changed. `battery` and `state` are replaced on each state transition.
All transitions return a new `ElectricVehicle` instance; the original is not
mutated.

This makes state history safe to log and makes simulation replay possible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from e3hybrid.core.exceptions import VehicleError
from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.vehicle.battery import Battery
from e3hybrid.vehicle.energy import EnergyModel
from e3hybrid.vehicle.state import VehicleConstraints, VehicleState
from e3hybrid.vehicle.types import VehicleId


@dataclass(slots=True)
class ElectricVehicle:
    """Entity representing a single electric vehicle during simulation.

    The vehicle depends on the `Battery` and `EnergyModel` interfaces, not
    on any concrete implementation. This allows different battery types and
    energy models to be evaluated without changing the vehicle entity.

    Attributes
    ----------
    vehicle_id:
        Unique identifier within the simulation run.
    constraints:
        Operational limits (min/max SoC, max speed, max payload).
    battery:
        Current battery state. Replaced on every energy transaction.
    state:
        Current simulation-time state. Replaced every tick.
    energy_model:
        Energy consumption model. Injected at construction, never changed.
    metadata:
        Optional read-only annotations (e.g., vehicle type, origin).
    """

    vehicle_id: VehicleId
    constraints: VehicleConstraints
    battery: Battery
    state: VehicleState
    energy_model: EnergyModel
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        """Validate consistency of vehicle parameters at construction."""

        if not str(self.vehicle_id).strip():
            raise VehicleError("vehicle_id must be non-empty")

        # Battery capacity must match the constraint ceiling.
        if abs(self.battery.capacity_kwh - self.constraints.max_soc_kwh) > 1e-9:
            raise VehicleError(
                f"battery capacity_kwh ({self.battery.capacity_kwh}) must"
                f" equal constraints.max_soc_kwh ({self.constraints.max_soc_kwh})"
            )

        # Initial SoC must be within constraint bounds.
        if self.state.soc_kwh < self.constraints.min_soc_kwh:
            raise VehicleError(
                f"initial soc_kwh ({self.state.soc_kwh}) is below"
                f" min_soc_kwh ({self.constraints.min_soc_kwh})"
            )
        if self.state.soc_kwh > self.constraints.max_soc_kwh:
            raise VehicleError(
                f"initial soc_kwh ({self.state.soc_kwh}) exceeds"
                f" max_soc_kwh ({self.constraints.max_soc_kwh})"
            )

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    @property
    def soc_kwh(self) -> float:
        """Current battery state of charge in kWh."""

        return self.battery.soc_kwh

    @property
    def soc_fraction(self) -> float:
        """Current state of charge as a fraction of capacity (0.0–1.0)."""

        return self.battery.soc_fraction

    @property
    def is_below_min_soc(self) -> bool:
        """True when SoC is at or below the minimum operational threshold."""

        return self.battery.soc_kwh <= self.constraints.min_soc_kwh

    @property
    def can_depart(self) -> bool:
        """True when SoC is above the minimum threshold and vehicle is not charging."""

        return (
            not self.is_below_min_soc
            and not self.state.is_charging
        )

    # ------------------------------------------------------------------
    # State transitions (return new instances — no mutation)
    # ------------------------------------------------------------------

    def traverse_edge(
        self,
        edge_id: EdgeId,
        target_node: NodeId,
        speed_mps: float,
        distance_m: float,
        acceleration_mps2: float = 0.0,
        grade: float = 0.0,
        duration_s: float | None = None,
    ) -> "ElectricVehicle":
        """Return an updated vehicle after traversing a road segment.

        Delegates energy computation entirely to `self.energy_model`. Does not
        know how energy is calculated.

        Parameters
        ----------
        edge_id:
            The edge being traversed.
        target_node:
            The node at the end of the edge.
        speed_mps:
            Speed during traversal in m/s.
        distance_m:
            Segment length in metres.
        acceleration_mps2:
            Average acceleration during traversal. 0.0 = constant speed.
        grade:
            Road slope (rise / run). 0.0 = flat.
        duration_s:
            Traversal time in seconds. None = computed from distance/speed.

        Returns
        -------
        ElectricVehicle:
            New vehicle instance with updated battery, position, and state.

        Raises
        ------
        VehicleError:
            If speed exceeds max_speed_mps, or if energy cannot be discharged.
        NotImplementedError:
            Propagated from the energy model when equations are not yet
            implemented (Phase 3 Stage 1).
        """

        if speed_mps > self.constraints.max_speed_mps:
            raise VehicleError(
                f"speed_mps ({speed_mps}) exceeds"
                f" max_speed_mps ({self.constraints.max_speed_mps})"
            )

        energy_kwh = self.energy_model.compute_energy_kwh(
            speed_mps=speed_mps,
            distance_m=distance_m,
            acceleration_mps2=acceleration_mps2,
            grade=grade,
            duration_s=duration_s,
        )

        if not self.battery.can_discharge(energy_kwh):
            raise VehicleError(
                f"insufficient battery: need {energy_kwh:.4f} kWh,"
                f" have {self.battery.soc_kwh:.4f} kWh"
            )

        new_battery = self.battery.discharge(energy_kwh)
        elapsed = duration_s if duration_s is not None else (
            distance_m / speed_mps if speed_mps > 0 else 0.0
        )
        new_state = VehicleState(
            current_node=target_node,
            current_edge=edge_id,
            soc_kwh=new_battery.soc_kwh,
            speed_mps=speed_mps,
            acceleration_mps2=acceleration_mps2,
            distance_travelled_m=self.state.distance_travelled_m + distance_m,
            time_elapsed_s=self.state.time_elapsed_s + elapsed,
            is_charging=False,
        )

        return ElectricVehicle(
            vehicle_id=self.vehicle_id,
            constraints=self.constraints,
            battery=new_battery,
            state=new_state,
            energy_model=self.energy_model,
            metadata=self.metadata,
        )

    def update_state(self, state: VehicleState) -> "ElectricVehicle":
        """Return a copy with a directly-set state (e.g., from SUMO sync).

        Used when the simulator core writes back authoritative position and SoC
        received from a SUMO TraCI call. The energy model is not consulted.

        The battery is updated to match `state.soc_kwh`.

        Raises
        ------
        VehicleError:
            If the new SoC violates constraint bounds.
        """

        if state.soc_kwh < self.constraints.min_soc_kwh:
            raise VehicleError(
                f"updated soc_kwh ({state.soc_kwh}) is below"
                f" min_soc_kwh ({self.constraints.min_soc_kwh})"
            )
        if state.soc_kwh > self.constraints.max_soc_kwh:
            raise VehicleError(
                f"updated soc_kwh ({state.soc_kwh}) exceeds"
                f" max_soc_kwh ({self.constraints.max_soc_kwh})"
            )
        new_battery = self.battery.clone_with_soc(state.soc_kwh)
        return ElectricVehicle(
            vehicle_id=self.vehicle_id,
            constraints=self.constraints,
            battery=new_battery,
            state=state,
            energy_model=self.energy_model,
            metadata=self.metadata,
        )

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def to_state_dict(self) -> dict[str, Any]:
        """Serialize current simulation state for logging and checkpointing.

        Does not include the energy model (not serializable in Phase 3).
        """

        return {
            "vehicle_id": str(self.vehicle_id),
            "soc_kwh": self.battery.soc_kwh,
            "soc_fraction": self.battery.soc_fraction,
            "state": self.state.to_dict(),
            "constraints": self.constraints.to_dict(),
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"ElectricVehicle("
            f"id={self.vehicle_id!r}, "
            f"soc={self.battery.soc_kwh:.2f}/{self.battery.capacity_kwh:.2f} kWh, "
            f"node={self.state.current_node!r})"
        )
