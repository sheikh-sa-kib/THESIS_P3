"""Electric vehicle domain model.

This module provides the domain entities for representing electric vehicles
during simulation. It is independent of routing algorithms, communication,
emergency handling, and SUMO/TraCI.

Public interfaces
-----------------
- `ElectricVehicle`       – entity representing a single EV
- `VehicleState`          – simulation-time state (position, SoC, speed, …)
- `VehicleConstraints`    – operational constraints (min/max SoC, max speed, …)
- `Battery` (Protocol)    – battery state interface
- `SimpleBattery`         – linear capacity battery implementation
- `EnergyModel` (Protocol)– energy consumption interface
- `FioriEnergyModel`      – Fiori et al. (2016) physics-based model (stub)
- `VehicleFactory`        – creates vehicles from validated config
- `VehicleValidator`      – validates vehicle consistency

Design philosophy
-----------------
All abstractions follow the same interface-based design as `CostProvider`:

- `EnergyModel` is a Protocol — routing algorithms never import a concrete
  energy model. Future phases can add `PolynomialEnergyModel`, `LinearEnergyModel`,
  `MLEnergyModel` without changing any dependent code.
- `Battery` is a Protocol — battery chemistry and degradation models can be
  swapped independently.
- Future: `CommunicationProtocol`, `EmergencyPolicy`, `DecisionStrategy` will
  follow the same pattern.

This keeps the framework extensible and makes it a research platform rather
than a one-off implementation.
"""

from e3hybrid.vehicle.battery import Battery, SimpleBattery
from e3hybrid.vehicle.energy import EnergyModel, FioriEnergyModel
from e3hybrid.vehicle.entity import ElectricVehicle
from e3hybrid.vehicle.factory import VehicleFactory
from e3hybrid.vehicle.state import VehicleConstraints, VehicleState
from e3hybrid.vehicle.types import VehicleId
from e3hybrid.vehicle.validation import VehicleValidationReport, VehicleValidator

__all__ = [
    "Battery",
    "ElectricVehicle",
    "EnergyModel",
    "FioriEnergyModel",
    "SimpleBattery",
    "VehicleConstraints",
    "VehicleFactory",
    "VehicleId",
    "VehicleState",
    "VehicleValidationReport",
    "VehicleValidator",
]
