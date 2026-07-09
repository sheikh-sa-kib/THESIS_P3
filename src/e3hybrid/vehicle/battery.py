"""Battery interface and implementations for electric vehicles.

Design
------
`Battery` is a Protocol. The vehicle entity and energy model depend only on
this interface. Concrete battery implementations (linear, degradation-aware,
chemistry-specific) are plugged in at construction time through the
`VehicleFactory`.

Why a Protocol and not an ABC?
Consistent with `CostProvider` and `EnergyModel`: structural typing lets any
class that satisfies the interface be used without inheriting from a base class.
This is cleaner for testing (plain dataclasses can act as batteries in tests)
and avoids coupling to an inheritance hierarchy that would be hard to change
later.

Current implementations
-----------------------
- `SimpleBattery`: linear capacity model. Capacity is fixed; no degradation,
  temperature effects, or C-rate derating. Suitable for Phase 3 and early
  simulation runs where battery chemistry is not the research variable.

Future implementations (not in Phase 3)
-----------------------------------------
- `DegradationBattery`: capacity fade model from cycling.
- `TemperatureAwareBattery`: capacity and efficiency as functions of temperature.
- `ChemistryBattery`: Li-ion, LFP, NMC with different charge curves.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from e3hybrid.core.exceptions import VehicleError


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class Battery(Protocol):
    """Interface that all battery implementations must satisfy.

    Routing algorithms and simulation components depend only on this interface.
    They must never import a concrete battery class directly.

    Properties
    ----------
    capacity_kwh:
        Nominal usable battery capacity in kWh. Read-only structural property.
    soc_kwh:
        Current state of charge in kWh. Updated by `discharge` and `charge`.
    soc_fraction:
        Current state of charge as a fraction of capacity (0.0 to 1.0).

    Methods
    -------
    discharge(delta_kwh):
        Remove energy from the battery. Raises `VehicleError` if this would
        drive SoC below zero.
    charge(delta_kwh):
        Add energy to the battery. Raises `VehicleError` if this would exceed
        capacity.
    can_discharge(delta_kwh):
        Return True if `delta_kwh` can be removed without driving SoC below
        zero.
    clone_with_soc(soc_kwh):
        Return a new Battery instance with the given SoC and the same
        structural parameters. Used by the simulation to snapshot state.
    """

    @property
    def capacity_kwh(self) -> float:
        """Nominal usable battery capacity in kWh."""
        ...

    @property
    def soc_kwh(self) -> float:
        """Current state of charge in kWh."""
        ...

    @property
    def soc_fraction(self) -> float:
        """Current state of charge as a fraction of capacity (0.0–1.0)."""
        ...

    def discharge(self, delta_kwh: float) -> "Battery":
        """Remove energy and return updated battery.

        Parameters
        ----------
        delta_kwh:
            Energy to remove in kWh. Must be positive.

        Returns
        -------
        Battery:
            New Battery instance with updated SoC.

        Raises
        ------
        VehicleError:
            If `delta_kwh` is not positive, or if it would reduce SoC below 0.
        """
        ...

    def charge(self, delta_kwh: float) -> "Battery":
        """Add energy and return updated battery.

        Parameters
        ----------
        delta_kwh:
            Energy to add in kWh. Must be positive.

        Returns
        -------
        Battery:
            New Battery instance with updated SoC.

        Raises
        ------
        VehicleError:
            If `delta_kwh` is not positive, or if it would exceed capacity.
        """
        ...

    def can_discharge(self, delta_kwh: float) -> bool:
        """Return True if `delta_kwh` can be removed without SoC going below 0."""
        ...

    def clone_with_soc(self, soc_kwh: float) -> "Battery":
        """Return a new Battery with the same parameters but different SoC.

        Used by the simulator to snapshot or restore battery state.

        Raises
        ------
        VehicleError:
            If `soc_kwh` is negative or exceeds capacity.
        """
        ...


# ---------------------------------------------------------------------------
# Simple linear battery implementation
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SimpleBattery:
    """Linear capacity battery with no degradation or temperature effects.

    Suitable for Phase 3 and early simulation runs. The research variable in
    this thesis is routing and swarm coordination, not battery chemistry.
    Battery degradation can be introduced later as a `DegradationBattery`
    implementation through the same `Battery` interface.

    Parameters
    ----------
    capacity_kwh:
        Nominal usable capacity in kWh. Must be positive.
    _soc_kwh:
        Current state of charge in kWh. Must be in [0, capacity_kwh].
        Set via `create()` or `clone_with_soc()`.
    """

    _capacity_kwh: float
    _soc_kwh: float

    def __post_init__(self) -> None:
        """Validate battery parameters."""

        if self._capacity_kwh <= 0:
            raise VehicleError("battery capacity_kwh must be positive")
        if self._soc_kwh < 0:
            raise VehicleError("battery soc_kwh must be non-negative")
        if self._soc_kwh > self._capacity_kwh:
            raise VehicleError(
                f"battery soc_kwh ({self._soc_kwh}) exceeds"
                f" capacity_kwh ({self._capacity_kwh})"
            )

    @classmethod
    def create(cls, capacity_kwh: float, initial_soc_kwh: float) -> "SimpleBattery":
        """Create a SimpleBattery with the given capacity and initial SoC.

        Parameters
        ----------
        capacity_kwh:
            Total usable capacity in kWh.
        initial_soc_kwh:
            Starting state of charge in kWh. Must be in [0, capacity_kwh].
        """

        return cls(_capacity_kwh=capacity_kwh, _soc_kwh=initial_soc_kwh)

    # ------------------------------------------------------------------
    # Protocol properties
    # ------------------------------------------------------------------

    @property
    def capacity_kwh(self) -> float:
        """Nominal usable battery capacity in kWh."""

        return self._capacity_kwh

    @property
    def soc_kwh(self) -> float:
        """Current state of charge in kWh."""

        return self._soc_kwh

    @property
    def soc_fraction(self) -> float:
        """Current state of charge as a fraction of capacity (0.0–1.0)."""

        return self._soc_kwh / self._capacity_kwh

    # ------------------------------------------------------------------
    # Protocol methods
    # ------------------------------------------------------------------

    def discharge(self, delta_kwh: float) -> "SimpleBattery":
        """Remove energy and return updated battery."""

        if delta_kwh <= 0:
            raise VehicleError("discharge delta_kwh must be positive")
        new_soc = self._soc_kwh - delta_kwh
        if new_soc < 0:
            raise VehicleError(
                f"cannot discharge {delta_kwh:.3f} kWh from battery with"
                f" {self._soc_kwh:.3f} kWh remaining"
            )
        return SimpleBattery(_capacity_kwh=self._capacity_kwh, _soc_kwh=new_soc)

    def charge(self, delta_kwh: float) -> "SimpleBattery":
        """Add energy and return updated battery."""

        if delta_kwh <= 0:
            raise VehicleError("charge delta_kwh must be positive")
        new_soc = self._soc_kwh + delta_kwh
        if new_soc > self._capacity_kwh:
            raise VehicleError(
                f"cannot charge {delta_kwh:.3f} kWh into battery with"
                f" {self._capacity_kwh - self._soc_kwh:.3f} kWh headroom"
            )
        return SimpleBattery(_capacity_kwh=self._capacity_kwh, _soc_kwh=new_soc)

    def can_discharge(self, delta_kwh: float) -> bool:
        """Return True if `delta_kwh` can be removed without SoC going below 0."""

        return delta_kwh > 0 and self._soc_kwh >= delta_kwh

    def clone_with_soc(self, soc_kwh: float) -> "SimpleBattery":
        """Return a new SimpleBattery with the same capacity but different SoC."""

        return SimpleBattery(_capacity_kwh=self._capacity_kwh, _soc_kwh=soc_kwh)
