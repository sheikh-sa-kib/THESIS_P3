"""Unit tests for the electric vehicle domain model (Phase 3)."""

import pytest

from e3hybrid.core.exceptions import VehicleError
from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.vehicle import (
    ElectricVehicle,
    FioriEnergyModel,
    SimpleBattery,
    VehicleConstraints,
    VehicleFactory,
    VehicleId,
    VehicleState,
    VehicleValidator,
)


# ---------------------------------------------------------------------------
# Battery tests
# ---------------------------------------------------------------------------


def test_simple_battery_create_and_query() -> None:
    """SimpleBattery should store capacity and SoC correctly."""

    battery = SimpleBattery.create(capacity_kwh=50.0, initial_soc_kwh=40.0)

    assert battery.capacity_kwh == 50.0
    assert battery.soc_kwh == 40.0
    assert battery.soc_fraction == pytest.approx(0.8)


def test_simple_battery_discharge() -> None:
    """Discharging should reduce SoC."""

    battery = SimpleBattery.create(capacity_kwh=50.0, initial_soc_kwh=40.0)
    new_battery = battery.discharge(10.0)

    assert new_battery.soc_kwh == pytest.approx(30.0)
    assert new_battery.capacity_kwh == 50.0


def test_simple_battery_charge() -> None:
    """Charging should increase SoC."""

    battery = SimpleBattery.create(capacity_kwh=50.0, initial_soc_kwh=30.0)
    new_battery = battery.charge(10.0)

    assert new_battery.soc_kwh == pytest.approx(40.0)


def test_simple_battery_rejects_overdischarge() -> None:
    """Discharging more than available SoC should raise VehicleError."""

    battery = SimpleBattery.create(capacity_kwh=50.0, initial_soc_kwh=5.0)

    with pytest.raises(VehicleError, match="cannot discharge"):
        battery.discharge(10.0)


def test_simple_battery_rejects_overcharge() -> None:
    """Charging beyond capacity should raise VehicleError."""

    battery = SimpleBattery.create(capacity_kwh=50.0, initial_soc_kwh=45.0)

    with pytest.raises(VehicleError, match="cannot charge"):
        battery.charge(10.0)


def test_simple_battery_can_discharge_check() -> None:
    """can_discharge should correctly report feasibility."""

    battery = SimpleBattery.create(capacity_kwh=50.0, initial_soc_kwh=15.0)

    assert battery.can_discharge(10.0) is True
    assert battery.can_discharge(15.0) is True
    assert battery.can_discharge(20.0) is False


def test_simple_battery_clone_with_soc() -> None:
    """clone_with_soc should preserve capacity."""

    battery = SimpleBattery.create(capacity_kwh=50.0, initial_soc_kwh=20.0)
    cloned = battery.clone_with_soc(35.0)

    assert cloned.capacity_kwh == 50.0
    assert cloned.soc_kwh == 35.0


def test_simple_battery_rejects_negative_capacity() -> None:
    """Negative or zero capacity should be rejected."""

    with pytest.raises(VehicleError, match="capacity_kwh"):
        SimpleBattery.create(capacity_kwh=0.0, initial_soc_kwh=0.0)


def test_simple_battery_rejects_negative_soc() -> None:
    """Negative SoC should be rejected."""

    with pytest.raises(VehicleError, match="soc_kwh"):
        SimpleBattery.create(capacity_kwh=50.0, initial_soc_kwh=-1.0)


def test_simple_battery_rejects_soc_exceeding_capacity() -> None:
    """Initial SoC exceeding capacity should be rejected."""

    with pytest.raises(VehicleError, match="exceeds capacity"):
        SimpleBattery.create(capacity_kwh=50.0, initial_soc_kwh=60.0)


# ---------------------------------------------------------------------------
# VehicleState and VehicleConstraints tests
# ---------------------------------------------------------------------------


def test_vehicle_constraints_from_dict() -> None:
    """VehicleConstraints should deserialize from a dictionary."""

    data = {
        "min_soc_kwh": 5.0,
        "max_soc_kwh": 50.0,
        "max_speed_mps": 35.0,
        "max_payload_kg": 200.0,
    }
    constraints = VehicleConstraints.from_dict(data)

    assert constraints.min_soc_kwh == 5.0
    assert constraints.max_soc_kwh == 50.0
    assert constraints.max_speed_mps == 35.0
    assert constraints.max_payload_kg == 200.0


def test_vehicle_constraints_rejects_invalid_bounds() -> None:
    """min_soc_kwh >= max_soc_kwh should be rejected."""

    with pytest.raises(VehicleError, match="less than max_soc_kwh"):
        VehicleConstraints(
            min_soc_kwh=50.0,
            max_soc_kwh=50.0,
            max_speed_mps=35.0,
        )


def test_vehicle_state_to_dict() -> None:
    """VehicleState should serialize to a dictionary."""

    state = VehicleState(
        current_node=NodeId("A"),
        current_edge=EdgeId("AB"),
        soc_kwh=30.0,
        speed_mps=15.0,
        acceleration_mps2=0.5,
        distance_travelled_m=1500.0,
        time_elapsed_s=120.0,
        is_charging=False,
    )
    data = state.to_dict()

    assert data["current_node"] == "A"
    assert data["current_edge"] == "AB"
    assert data["soc_kwh"] == 30.0
    assert data["speed_mps"] == 15.0


def test_vehicle_state_rejects_negative_values() -> None:
    """Negative speed, SoC, distance, or time should be rejected."""

    with pytest.raises(VehicleError, match="soc_kwh"):
        VehicleState(
            current_node=NodeId("A"),
            current_edge=None,
            soc_kwh=-1.0,
            speed_mps=0.0,
        )

    with pytest.raises(VehicleError, match="speed_mps"):
        VehicleState(
            current_node=NodeId("A"),
            current_edge=None,
            soc_kwh=10.0,
            speed_mps=-1.0,
        )


# ---------------------------------------------------------------------------
# FioriEnergyModel tests (stub only — equations not implemented)
# ---------------------------------------------------------------------------


def test_fiori_energy_model_validates_parameters() -> None:
    """FioriEnergyModel should validate parameter bounds at construction."""

    # Valid parameters should pass.
    model = FioriEnergyModel(
        vehicle_mass_kg=1500.0,
        drag_coefficient=0.28,
        frontal_area_m2=2.2,
        rolling_resistance_coeff=0.012,
        drivetrain_efficiency=0.9,
        regen_efficiency=0.65,
        auxiliary_power_w=300.0,
    )
    assert model.vehicle_mass_kg == 1500.0


def test_fiori_energy_model_rejects_negative_mass() -> None:
    """Negative vehicle mass should be rejected."""

    with pytest.raises(VehicleError, match="vehicle_mass_kg"):
        FioriEnergyModel(
            vehicle_mass_kg=0.0,
            drag_coefficient=0.28,
            frontal_area_m2=2.2,
            rolling_resistance_coeff=0.012,
            drivetrain_efficiency=0.9,
            regen_efficiency=0.65,
            auxiliary_power_w=300.0,
        )


def test_fiori_energy_model_rejects_invalid_efficiency() -> None:
    """Efficiencies outside (0, 1] should be rejected."""

    with pytest.raises(VehicleError, match="drivetrain_efficiency"):
        FioriEnergyModel(
            vehicle_mass_kg=1500.0,
            drag_coefficient=0.28,
            frontal_area_m2=2.2,
            rolling_resistance_coeff=0.012,
            drivetrain_efficiency=1.5,
            regen_efficiency=0.65,
            auxiliary_power_w=300.0,
        )


def test_fiori_energy_model_compute_raises_not_implemented() -> None:
    """compute_energy_kwh should raise NotImplementedError in Phase 3 Stage 1."""

    model = FioriEnergyModel(
        vehicle_mass_kg=1500.0,
        drag_coefficient=0.28,
        frontal_area_m2=2.2,
        rolling_resistance_coeff=0.012,
        drivetrain_efficiency=0.9,
        regen_efficiency=0.65,
        auxiliary_power_w=300.0,
    )

    with pytest.raises(NotImplementedError, match="not yet implemented"):
        model.compute_energy_kwh(speed_mps=15.0, distance_m=1000.0)


def test_fiori_energy_model_validates_inputs() -> None:
    """compute_energy_kwh should reject negative speed or distance."""

    model = FioriEnergyModel(
        vehicle_mass_kg=1500.0,
        drag_coefficient=0.28,
        frontal_area_m2=2.2,
        rolling_resistance_coeff=0.012,
        drivetrain_efficiency=0.9,
        regen_efficiency=0.65,
        auxiliary_power_w=300.0,
    )

    with pytest.raises(VehicleError, match="speed_mps"):
        model.compute_energy_kwh(speed_mps=-1.0, distance_m=1000.0)

    with pytest.raises(VehicleError, match="distance_m"):
        model.compute_energy_kwh(speed_mps=15.0, distance_m=-100.0)


# ---------------------------------------------------------------------------
# ElectricVehicle tests
# ---------------------------------------------------------------------------


def test_electric_vehicle_creation() -> None:
    """ElectricVehicle should construct with valid parameters."""

    battery = SimpleBattery.create(capacity_kwh=50.0, initial_soc_kwh=40.0)
    constraints = VehicleConstraints(
        min_soc_kwh=5.0,
        max_soc_kwh=50.0,
        max_speed_mps=35.0,
    )
    state = VehicleState(
        current_node=NodeId("A"),
        current_edge=None,
        soc_kwh=40.0,
        speed_mps=0.0,
    )
    energy_model = FioriEnergyModel(
        vehicle_mass_kg=1500.0,
        drag_coefficient=0.28,
        frontal_area_m2=2.2,
        rolling_resistance_coeff=0.012,
        drivetrain_efficiency=0.9,
        regen_efficiency=0.65,
        auxiliary_power_w=300.0,
    )

    vehicle = ElectricVehicle(
        vehicle_id=VehicleId("v1"),
        constraints=constraints,
        battery=battery,
        state=state,
        energy_model=energy_model,
        metadata={},
    )

    assert vehicle.vehicle_id == VehicleId("v1")
    assert vehicle.soc_kwh == 40.0
    assert vehicle.soc_fraction == pytest.approx(0.8)


def test_electric_vehicle_rejects_mismatched_capacity() -> None:
    """Battery capacity must match constraints.max_soc_kwh."""

    battery = SimpleBattery.create(capacity_kwh=50.0, initial_soc_kwh=40.0)
    constraints = VehicleConstraints(
        min_soc_kwh=5.0,
        max_soc_kwh=60.0,  # Mismatch!
        max_speed_mps=35.0,
    )
    state = VehicleState(
        current_node=NodeId("A"),
        current_edge=None,
        soc_kwh=40.0,
        speed_mps=0.0,
    )
    energy_model = FioriEnergyModel(
        vehicle_mass_kg=1500.0,
        drag_coefficient=0.28,
        frontal_area_m2=2.2,
        rolling_resistance_coeff=0.012,
        drivetrain_efficiency=0.9,
        regen_efficiency=0.65,
        auxiliary_power_w=300.0,
    )

    with pytest.raises(VehicleError, match="capacity_kwh.*must equal"):
        ElectricVehicle(
            vehicle_id=VehicleId("v1"),
            constraints=constraints,
            battery=battery,
            state=state,
            energy_model=energy_model,
            metadata={},
        )


def test_electric_vehicle_can_depart_property() -> None:
    """can_depart should be True when SoC > min and not charging."""

    battery = SimpleBattery.create(capacity_kwh=50.0, initial_soc_kwh=40.0)
    constraints = VehicleConstraints(
        min_soc_kwh=5.0,
        max_soc_kwh=50.0,
        max_speed_mps=35.0,
    )
    state = VehicleState(
        current_node=NodeId("A"),
        current_edge=None,
        soc_kwh=40.0,
        speed_mps=0.0,
    )
    energy_model = FioriEnergyModel(
        vehicle_mass_kg=1500.0,
        drag_coefficient=0.28,
        frontal_area_m2=2.2,
        rolling_resistance_coeff=0.012,
        drivetrain_efficiency=0.9,
        regen_efficiency=0.65,
        auxiliary_power_w=300.0,
    )

    vehicle = ElectricVehicle(
        vehicle_id=VehicleId("v1"),
        constraints=constraints,
        battery=battery,
        state=state,
        energy_model=energy_model,
        metadata={},
    )

    assert vehicle.can_depart is True
    assert vehicle.is_below_min_soc is False


def test_electric_vehicle_to_state_dict() -> None:
    """to_state_dict should serialize current vehicle state."""

    battery = SimpleBattery.create(capacity_kwh=50.0, initial_soc_kwh=30.0)
    constraints = VehicleConstraints(
        min_soc_kwh=5.0,
        max_soc_kwh=50.0,
        max_speed_mps=35.0,
    )
    state = VehicleState(
        current_node=NodeId("B"),
        current_edge=EdgeId("AB"),
        soc_kwh=30.0,
        speed_mps=15.0,
    )
    energy_model = FioriEnergyModel(
        vehicle_mass_kg=1500.0,
        drag_coefficient=0.28,
        frontal_area_m2=2.2,
        rolling_resistance_coeff=0.012,
        drivetrain_efficiency=0.9,
        regen_efficiency=0.65,
        auxiliary_power_w=300.0,
    )

    vehicle = ElectricVehicle(
        vehicle_id=VehicleId("v2"),
        constraints=constraints,
        battery=battery,
        state=state,
        energy_model=energy_model,
        metadata={"type": "compact"},
    )

    data = vehicle.to_state_dict()

    assert data["vehicle_id"] == "v2"
    assert data["soc_kwh"] == 30.0
    assert data["soc_fraction"] == pytest.approx(0.6)
    assert data["state"]["current_node"] == "B"


# ---------------------------------------------------------------------------
# VehicleFactory tests
# ---------------------------------------------------------------------------


def test_vehicle_factory_creates_from_config() -> None:
    """VehicleFactory should create a vehicle from a valid config dict."""

    config = {
        "battery": {
            "capacity_kwh": 50.0,
            "initial_soc_kwh": 40.0,
        },
        "constraints": {
            "min_soc_kwh": 5.0,
            "max_soc_kwh": 50.0,
            "max_speed_mps": 35.0,
        },
        "energy_model": {
            "type": "fiori",
            "vehicle_mass_kg": 1500.0,
            "drag_coefficient": 0.28,
            "frontal_area_m2": 2.2,
            "rolling_resistance_coeff": 0.012,
            "drivetrain_efficiency": 0.9,
            "regen_efficiency": 0.65,
            "auxiliary_power_w": 300.0,
        },
        "metadata": {"type": "compact"},
    }

    vehicle = VehicleFactory.create_from_config(
        vehicle_id="v1",
        initial_node=NodeId("A"),
        config=config,
    )

    assert vehicle.vehicle_id == VehicleId("v1")
    assert vehicle.soc_kwh == 40.0
    assert vehicle.state.current_node == NodeId("A")


def test_vehicle_factory_rejects_missing_battery_config() -> None:
    """Factory should reject config missing required sections."""

    config = {
        "constraints": {
            "min_soc_kwh": 5.0,
            "max_soc_kwh": 50.0,
            "max_speed_mps": 35.0,
        },
        "energy_model": {
            "type": "fiori",
            "vehicle_mass_kg": 1500.0,
            "drag_coefficient": 0.28,
            "frontal_area_m2": 2.2,
            "rolling_resistance_coeff": 0.012,
            "drivetrain_efficiency": 0.9,
            "regen_efficiency": 0.65,
            "auxiliary_power_w": 300.0,
        },
    }

    with pytest.raises(VehicleError, match="missing required config key: 'battery'"):
        VehicleFactory.create_from_config(
            vehicle_id="v1",
            initial_node=NodeId("A"),
            config=config,
        )


def test_vehicle_factory_rejects_unsupported_energy_type() -> None:
    """Factory should reject unsupported energy_model.type."""

    config = {
        "battery": {
            "capacity_kwh": 50.0,
            "initial_soc_kwh": 40.0,
        },
        "constraints": {
            "min_soc_kwh": 5.0,
            "max_soc_kwh": 50.0,
            "max_speed_mps": 35.0,
        },
        "energy_model": {
            "type": "polynomial",  # Not supported in Phase 3
        },
    }

    with pytest.raises(VehicleError, match="unsupported energy_model.type"):
        VehicleFactory.create_from_config(
            vehicle_id="v1",
            initial_node=NodeId("A"),
            config=config,
        )


# ---------------------------------------------------------------------------
# VehicleValidator tests
# ---------------------------------------------------------------------------


def test_vehicle_validator_accepts_valid_vehicle() -> None:
    """VehicleValidator should return is_valid=True for a valid vehicle."""

    battery = SimpleBattery.create(capacity_kwh=50.0, initial_soc_kwh=40.0)
    constraints = VehicleConstraints(
        min_soc_kwh=5.0,
        max_soc_kwh=50.0,
        max_speed_mps=35.0,
    )
    state = VehicleState(
        current_node=NodeId("A"),
        current_edge=None,
        soc_kwh=40.0,
        speed_mps=15.0,
    )
    energy_model = FioriEnergyModel(
        vehicle_mass_kg=1500.0,
        drag_coefficient=0.28,
        frontal_area_m2=2.2,
        rolling_resistance_coeff=0.012,
        drivetrain_efficiency=0.9,
        regen_efficiency=0.65,
        auxiliary_power_w=300.0,
    )

    vehicle = ElectricVehicle(
        vehicle_id=VehicleId("v1"),
        constraints=constraints,
        battery=battery,
        state=state,
        energy_model=energy_model,
        metadata={},
    )

    report = VehicleValidator().validate(vehicle)

    assert report.is_valid is True
    assert not report.errors


def test_vehicle_validator_detects_soc_below_min() -> None:
    """Validator should detect SoC below min_soc_kwh as an error."""

    battery = SimpleBattery.create(capacity_kwh=50.0, initial_soc_kwh=3.0)
    constraints = VehicleConstraints(
        min_soc_kwh=5.0,
        max_soc_kwh=50.0,
        max_speed_mps=35.0,
    )
    state = VehicleState(
        current_node=NodeId("A"),
        current_edge=None,
        soc_kwh=3.0,
        speed_mps=0.0,
    )
    energy_model = FioriEnergyModel(
        vehicle_mass_kg=1500.0,
        drag_coefficient=0.28,
        frontal_area_m2=2.2,
        rolling_resistance_coeff=0.012,
        drivetrain_efficiency=0.9,
        regen_efficiency=0.65,
        auxiliary_power_w=300.0,
    )

    vehicle = ElectricVehicle(
        vehicle_id=VehicleId("v1"),
        constraints=constraints,
        battery=battery,
        state=state,
        energy_model=energy_model,
        metadata={},
    )

    report = VehicleValidator().validate(vehicle)

    assert report.is_valid is False
    assert any("below min_soc_kwh" in e for e in report.errors)


def test_vehicle_validator_raises_on_invalid_vehicle() -> None:
    """validate_or_raise should raise VehicleError on validation failure."""

    battery = SimpleBattery.create(capacity_kwh=50.0, initial_soc_kwh=55.0)
    constraints = VehicleConstraints(
        min_soc_kwh=5.0,
        max_soc_kwh=50.0,
        max_speed_mps=35.0,
    )
    # Battery has 55 kWh but max is 50 → should fail at ElectricVehicle construction
    # Let's bypass that and test validator separately by cloning battery with invalid SoC.
    battery_invalid = battery.clone_with_soc(55.0)

    state = VehicleState(
        current_node=NodeId("A"),
        current_edge=None,
        soc_kwh=55.0,
        speed_mps=0.0,
    )
    energy_model = FioriEnergyModel(
        vehicle_mass_kg=1500.0,
        drag_coefficient=0.28,
        frontal_area_m2=2.2,
        rolling_resistance_coeff=0.012,
        drivetrain_efficiency=0.9,
        regen_efficiency=0.65,
        auxiliary_power_w=300.0,
    )

    # Bypass __post_init__ by directly setting attributes (test only).
    vehicle = object.__new__(ElectricVehicle)
    object.__setattr__(vehicle, "vehicle_id", VehicleId("v1"))
    object.__setattr__(vehicle, "constraints", constraints)
    object.__setattr__(vehicle, "battery", battery_invalid)
    object.__setattr__(vehicle, "state", state)
    object.__setattr__(vehicle, "energy_model", energy_model)
    object.__setattr__(vehicle, "metadata", {})

    with pytest.raises(VehicleError, match="validation failed"):
        VehicleValidator().validate_or_raise(vehicle)
