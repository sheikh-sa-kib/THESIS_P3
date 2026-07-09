"""Vehicle factory for creating vehicles from validated configuration."""

from __future__ import annotations

from typing import Any, Mapping

from e3hybrid.core.exceptions import VehicleError
from e3hybrid.network.types import NodeId
from e3hybrid.vehicle.battery import SimpleBattery
from e3hybrid.vehicle.energy import FioriEnergyModel
from e3hybrid.vehicle.entity import ElectricVehicle
from e3hybrid.vehicle.state import VehicleConstraints, VehicleState
from e3hybrid.vehicle.types import VehicleId


class VehicleFactory:
    """Creates `ElectricVehicle` instances from validated configuration mappings.

    This factory centralises vehicle construction so that the same vehicle
    parameters can be reused across experiment runs without copying
    boilerplate code.

    Currently supports:
    - `SimpleBattery` (linear capacity, no degradation)
    - `FioriEnergyModel` (physics-based, stub in Phase 3 Stage 1)

    Future phases can extend this factory to support:
    - `DegradationBattery`
    - `TemperatureAwareBattery`
    - `PolynomialEnergyModel`
    - `LinearEnergyModel`
    - `MLEnergyModel`
    """

    @staticmethod
    def create_from_config(
        vehicle_id: str,
        initial_node: NodeId,
        config: Mapping[str, Any],
    ) -> ElectricVehicle:
        """Create an `ElectricVehicle` from a validated configuration mapping.

        Parameters
        ----------
        vehicle_id:
            Unique identifier for this vehicle.
        initial_node:
            Node where the vehicle starts.
        config:
            Configuration dictionary with vehicle parameters. Expected keys:

            battery:
                capacity_kwh: float
                initial_soc_kwh: float

            constraints:
                min_soc_kwh: float
                max_soc_kwh: float
                max_speed_mps: float
                max_payload_kg: float (optional, default 0.0)

            energy_model:
                type: "fiori"  (only supported type in Phase 3)
                vehicle_mass_kg: float
                drag_coefficient: float
                frontal_area_m2: float
                rolling_resistance_coeff: float
                drivetrain_efficiency: float
                regen_efficiency: float
                auxiliary_power_w: float
                air_density_kg_m3: float (optional, default 1.225)
                gravity_m_s2: float (optional, default 9.81)

            metadata: dict (optional)

        Returns
        -------
        ElectricVehicle:
            Fully constructed vehicle entity.

        Raises
        ------
        VehicleError:
            If required config keys are missing or values are invalid.
        """

        # ------------------------------------------------------------------
        # Battery
        # ------------------------------------------------------------------

        battery_config = _require_mapping(config, "battery")
        capacity_kwh = _require_positive_float(
            battery_config, "battery.capacity_kwh"
        )
        initial_soc_kwh = _require_non_negative_float(
            battery_config, "battery.initial_soc_kwh"
        )
        battery = SimpleBattery.create(
            capacity_kwh=capacity_kwh,
            initial_soc_kwh=initial_soc_kwh,
        )

        # ------------------------------------------------------------------
        # Constraints
        # ------------------------------------------------------------------

        constraints_config = _require_mapping(config, "constraints")
        constraints = VehicleConstraints.from_dict(constraints_config)

        # ------------------------------------------------------------------
        # Energy model
        # ------------------------------------------------------------------

        energy_config = _require_mapping(config, "energy_model")
        energy_type = _require_string(energy_config, "energy_model.type")
        if energy_type != "fiori":
            raise VehicleError(
                f"unsupported energy_model.type: '{energy_type}'."
                " Phase 3 supports only 'fiori'."
            )
        energy_model = FioriEnergyModel(
            vehicle_mass_kg=_require_positive_float(
                energy_config, "energy_model.vehicle_mass_kg"
            ),
            drag_coefficient=_require_positive_float(
                energy_config, "energy_model.drag_coefficient"
            ),
            frontal_area_m2=_require_positive_float(
                energy_config, "energy_model.frontal_area_m2"
            ),
            rolling_resistance_coeff=_require_positive_float(
                energy_config, "energy_model.rolling_resistance_coeff"
            ),
            drivetrain_efficiency=_require_bounded_float(
                energy_config, "energy_model.drivetrain_efficiency", 0.0, 1.0
            ),
            regen_efficiency=_require_bounded_float(
                energy_config, "energy_model.regen_efficiency", 0.0, 1.0
            ),
            auxiliary_power_w=_require_non_negative_float(
                energy_config, "energy_model.auxiliary_power_w"
            ),
            air_density_kg_m3=energy_config.get("air_density_kg_m3", 1.225),
            gravity_m_s2=energy_config.get("gravity_m_s2", 9.81),
        )

        # ------------------------------------------------------------------
        # Initial state
        # ------------------------------------------------------------------

        initial_state = VehicleState(
            current_node=initial_node,
            current_edge=None,
            soc_kwh=initial_soc_kwh,
            speed_mps=0.0,
            acceleration_mps2=0.0,
            distance_travelled_m=0.0,
            time_elapsed_s=0.0,
            is_charging=False,
        )

        # ------------------------------------------------------------------
        # Metadata
        # ------------------------------------------------------------------

        metadata = dict(config.get("metadata", {}))

        # ------------------------------------------------------------------
        # Construct vehicle
        # ------------------------------------------------------------------

        return ElectricVehicle(
            vehicle_id=VehicleId(vehicle_id),
            constraints=constraints,
            battery=battery,
            state=initial_state,
            energy_model=energy_model,
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _require_mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """Return a required mapping value or raise VehicleError."""

    if key not in data:
        raise VehicleError(f"missing required config key: '{key}'")
    value = data[key]
    if not isinstance(value, Mapping):
        raise VehicleError(f"config key '{key}' must be a mapping")
    return value


def _require_string(data: Mapping[str, Any], key: str) -> str:
    """Return a required non-empty string value or raise VehicleError."""

    if key not in data:
        raise VehicleError(f"missing required config key: '{key}'")
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        raise VehicleError(f"config key '{key}' must be a non-empty string")
    return value.strip()


def _require_positive_float(data: Mapping[str, Any], key: str) -> float:
    """Return a required positive float value or raise VehicleError."""

    if key not in data:
        raise VehicleError(f"missing required config key: '{key}'")
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise VehicleError(f"config key '{key}' must be a positive number")
    return float(value)


def _require_non_negative_float(data: Mapping[str, Any], key: str) -> float:
    """Return a required non-negative float value or raise VehicleError."""

    if key not in data:
        raise VehicleError(f"missing required config key: '{key}'")
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        raise VehicleError(f"config key '{key}' must be non-negative")
    return float(value)


def _require_bounded_float(
    data: Mapping[str, Any], key: str, lower: float, upper: float
) -> float:
    """Return a required float in [lower, upper] or raise VehicleError."""

    if key not in data:
        raise VehicleError(f"missing required config key: '{key}'")
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise VehicleError(f"config key '{key}' must be numeric")
    fval = float(value)
    if not (lower < fval <= upper):
        raise VehicleError(
            f"config key '{key}' must be in ({lower}, {upper}], got {fval}"
        )
    return fval
