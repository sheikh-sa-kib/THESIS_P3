"""Vehicle state and constraint models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from e3hybrid.core.exceptions import VehicleError
from e3hybrid.network.types import NodeId


@dataclass(frozen=True, slots=True)
class VehicleConstraints:
    """Operational constraints for an electric vehicle.

    These constraints are validated at vehicle construction and enforced by
    the simulation. Violations raise `VehicleError`.

    Attributes
    ----------
    min_soc_kwh:
        Minimum battery state of charge in kWh. Vehicle must not operate below
        this threshold. Typically 10–20% of capacity to preserve battery health.
    max_soc_kwh:
        Maximum battery state of charge in kWh. Must equal battery capacity.
    max_speed_mps:
        Maximum vehicle speed in metres per second. Legal or physical limit.
    max_payload_kg:
        Maximum payload mass in kilograms. Used by energy models that account
        for vehicle mass.
    """

    min_soc_kwh: float
    max_soc_kwh: float
    max_speed_mps: float
    max_payload_kg: float = 0.0

    def __post_init__(self) -> None:
        """Validate constraint values."""

        if self.min_soc_kwh < 0:
            raise VehicleError("min_soc_kwh must be non-negative")
        if self.max_soc_kwh <= 0:
            raise VehicleError("max_soc_kwh must be positive")
        if self.min_soc_kwh >= self.max_soc_kwh:
            raise VehicleError("min_soc_kwh must be less than max_soc_kwh")
        if self.max_speed_mps <= 0:
            raise VehicleError("max_speed_mps must be positive")
        if self.max_payload_kg < 0:
            raise VehicleError("max_payload_kg must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        """Serialize constraints to a JSON-compatible dictionary."""

        return {
            "min_soc_kwh": self.min_soc_kwh,
            "max_soc_kwh": self.max_soc_kwh,
            "max_speed_mps": self.max_speed_mps,
            "max_payload_kg": self.max_payload_kg,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "VehicleConstraints":
        """Create constraints from a serialized dictionary."""

        required_fields = ("min_soc_kwh", "max_soc_kwh", "max_speed_mps")
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            joined = ", ".join(missing_fields)
            raise VehicleError(
                f"serialized constraints missing field(s): {joined}"
            )
        return cls(
            min_soc_kwh=_non_negative_float(
                data["min_soc_kwh"], "constraints.min_soc_kwh"
            ),
            max_soc_kwh=_positive_float(
                data["max_soc_kwh"], "constraints.max_soc_kwh"
            ),
            max_speed_mps=_positive_float(
                data["max_speed_mps"], "constraints.max_speed_mps"
            ),
            max_payload_kg=_non_negative_float(
                data.get("max_payload_kg", 0.0), "constraints.max_payload_kg"
            ),
        )


@dataclass(frozen=True, slots=True)
class VehicleState:
    """Simulation-time state for an electric vehicle.

    Updated every simulation tick by the simulator core. Immutable; state
    transitions produce new `VehicleState` instances.

    Attributes
    ----------
    current_node:
        Node ID where the vehicle is currently located. `None` if the vehicle
        is between nodes on an edge.
    current_edge:
        Edge ID the vehicle is traversing. `None` if the vehicle is stationary
        at a node.
    soc_kwh:
        Current battery state of charge in kWh.
    speed_mps:
        Current speed in metres per second.
    acceleration_mps2:
        Current acceleration in metres per second squared. Used by physics-based
        energy models. May be `None` if the simulation does not track acceleration.
    distance_travelled_m:
        Cumulative distance travelled since simulation start, in metres.
    time_elapsed_s:
        Cumulative time elapsed since simulation start, in seconds.
    is_charging:
        True when the vehicle is stationary at a charging station. Charging
        logic is not yet implemented in Phase 3.
    """

    current_node: NodeId | None
    current_edge: Any | None  # EdgeId will be imported from network.types in future
    soc_kwh: float
    speed_mps: float
    acceleration_mps2: float | None = None
    distance_travelled_m: float = 0.0
    time_elapsed_s: float = 0.0
    is_charging: bool = False

    def __post_init__(self) -> None:
        """Validate state values."""

        if self.soc_kwh < 0:
            raise VehicleError("soc_kwh must be non-negative")
        if self.speed_mps < 0:
            raise VehicleError("speed_mps must be non-negative")
        if self.distance_travelled_m < 0:
            raise VehicleError("distance_travelled_m must be non-negative")
        if self.time_elapsed_s < 0:
            raise VehicleError("time_elapsed_s must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        """Serialize state to a JSON-compatible dictionary."""

        return {
            "current_node": str(self.current_node) if self.current_node else None,
            "current_edge": str(self.current_edge) if self.current_edge else None,
            "soc_kwh": self.soc_kwh,
            "speed_mps": self.speed_mps,
            "acceleration_mps2": self.acceleration_mps2,
            "distance_travelled_m": self.distance_travelled_m,
            "time_elapsed_s": self.time_elapsed_s,
            "is_charging": self.is_charging,
        }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _positive_float(value: Any, field_name: str) -> float:
    """Return a positive numeric value as a float."""

    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise VehicleError(f"{field_name} must be positive")
    return float(value)


def _non_negative_float(value: Any, field_name: str) -> float:
    """Return a non-negative numeric value as a float."""

    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        raise VehicleError(f"{field_name} must be non-negative")
    return float(value)
