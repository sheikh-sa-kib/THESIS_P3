"""Validation utilities for electric vehicles."""

from __future__ import annotations

from dataclasses import dataclass

from e3hybrid.core.exceptions import VehicleError
from e3hybrid.vehicle.entity import ElectricVehicle


@dataclass(frozen=True, slots=True)
class VehicleValidationReport:
    """Result of validating an electric vehicle.

    Attributes
    ----------
    vehicle_id:
        The vehicle identifier being validated.
    errors:
        Tuple of error messages. Empty when validation passes.
    warnings:
        Tuple of warning messages. Non-blocking issues for review.
    """

    vehicle_id: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        """Return True when the vehicle has no hard validation errors."""

        return not self.errors


class VehicleValidator:
    """Validate consistency of an `ElectricVehicle`.

    Validation checks:
    - Battery capacity matches constraint ceiling.
    - Current SoC is within [min_soc_kwh, max_soc_kwh].
    - Speed does not exceed max_speed_mps.
    - SoC is non-negative.

    Warnings:
    - SoC is at or below min_soc_kwh (vehicle cannot depart).
    - SoC is very low (< 5% of capacity) but above min threshold.
    """

    def validate(self, vehicle: ElectricVehicle) -> VehicleValidationReport:
        """Return a validation report for the vehicle without raising."""

        errors: list[str] = []
        warnings: list[str] = []

        # ------------------------------------------------------------------
        # Battery capacity vs constraint ceiling
        # ------------------------------------------------------------------

        if (
            abs(vehicle.battery.capacity_kwh - vehicle.constraints.max_soc_kwh)
            > 1e-9
        ):
            errors.append(
                f"battery capacity_kwh ({vehicle.battery.capacity_kwh:.3f})"
                f" does not match constraints.max_soc_kwh"
                f" ({vehicle.constraints.max_soc_kwh:.3f})"
            )

        # ------------------------------------------------------------------
        # Current SoC bounds
        # ------------------------------------------------------------------

        if vehicle.state.soc_kwh < 0:
            errors.append(f"soc_kwh is negative: {vehicle.state.soc_kwh:.3f}")

        if vehicle.state.soc_kwh < vehicle.constraints.min_soc_kwh:
            errors.append(
                f"soc_kwh ({vehicle.state.soc_kwh:.3f}) is below"
                f" min_soc_kwh ({vehicle.constraints.min_soc_kwh:.3f})"
            )

        if vehicle.state.soc_kwh > vehicle.constraints.max_soc_kwh:
            errors.append(
                f"soc_kwh ({vehicle.state.soc_kwh:.3f}) exceeds"
                f" max_soc_kwh ({vehicle.constraints.max_soc_kwh:.3f})"
            )

        # ------------------------------------------------------------------
        # Speed constraint
        # ------------------------------------------------------------------

        if vehicle.state.speed_mps > vehicle.constraints.max_speed_mps:
            errors.append(
                f"speed_mps ({vehicle.state.speed_mps:.2f}) exceeds"
                f" max_speed_mps ({vehicle.constraints.max_speed_mps:.2f})"
            )

        # ------------------------------------------------------------------
        # Warnings
        # ------------------------------------------------------------------

        if vehicle.state.soc_kwh <= vehicle.constraints.min_soc_kwh:
            warnings.append(
                f"soc_kwh is at or below min_soc_kwh"
                f" ({vehicle.constraints.min_soc_kwh:.3f}); vehicle cannot depart"
            )
        elif vehicle.state.soc_kwh < 0.05 * vehicle.battery.capacity_kwh:
            warnings.append(
                f"soc_kwh is very low ({vehicle.state.soc_kwh:.3f} kWh,"
                f" {vehicle.soc_fraction * 100:.1f}% of capacity)"
            )

        return VehicleValidationReport(
            vehicle_id=str(vehicle.vehicle_id),
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    def validate_or_raise(self, vehicle: ElectricVehicle) -> VehicleValidationReport:
        """Validate and raise `VehicleError` if any hard errors are found.

        Returns the report (including warnings) when the vehicle is valid.
        """

        report = self.validate(vehicle)
        if not report.is_valid:
            raise VehicleError(
                f"Vehicle validation failed for '{vehicle.vehicle_id}': "
                + "; ".join(report.errors)
            )
        return report
