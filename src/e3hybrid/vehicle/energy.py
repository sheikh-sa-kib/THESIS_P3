"""Energy consumption model interface and implementations.

Design
------
`EnergyModel` is a Protocol. Routing algorithms, the simulation core, and the
vehicle entity depend only on this interface. Concrete energy models are
plugged in at vehicle construction via the `VehicleFactory`.

Why Fiori et al. (2016)?
-------------------------
The Fiori model is physics-based and widely cited in EV routing literature:

  Fiori, C., Ahn, K., & Rakha, H. A. (2016).
  Power-based electric vehicle energy consumption model: Model development
  and validation.
  Applied Energy, 168, 257–268.
  https://doi.org/10.1016/j.apenergy.2016.01.097

Advantages over simplified linear models:

1. **Explicit physics** — rolling resistance, aerodynamic drag, grade, inertia,
   and regenerative braking are modelled from first principles. This makes the
   model interpretable and auditable.

2. **Speed-dependent nonlinearity** — aerodynamic drag scales with v² and
   dominates at highway speeds. Linear models (ΔE = α·d + β·v²·d) require
   pre-calibration for each speed regime; Fiori adapts automatically.

3. **Regenerative braking** — captures energy recovery on deceleration and
   downhill segments. This is critical for urban emergency scenarios where
   vehicles must repeatedly brake and accelerate.

4. **Grade support** — although Phase 3 treats all edges as flat (grade=0),
   the Fiori model is ready for Phase 4 when SUMO provides elevation data.

5. **Widely validated** — the paper reports validation against EPA drive
   cycles and real-world EV data (Nissan Leaf, Mitsubishi i-MiEV, others).
   Using a validated model reduces the risk of fabricated results.

6. **Literature-backed parameters** — vehicle mass, drag coefficient, frontal
   area, rolling resistance, drivetrain efficiency are drawn from published
   EV spec sheets. No hidden constants.

Computational complexity:
  O(1) per edge traversal — the model evaluates a closed-form algebraic
  expression (power = f(speed, acceleration, grade) × time). No iterative
  solvers or integration loops.

Limitations (addressed in design doc before implementation):
- Auxiliary loads (HVAC, electronics) are parameterized but not modelled
  dynamically. They are treated as a constant power offset.
- Battery efficiency is constant (no temperature, C-rate, or SoC-dependent
  losses). If battery efficiency becomes a research variable, a
  `TemperatureAwareBattery` can be introduced through the `Battery` Protocol.
- Road surface and tyre conditions are constant. Extensions can parameterise
  rolling resistance per edge type (asphalt, gravel, wet).

Extension points (future research):
- Polynomial models (e.g., NREL polynomial regression over EPA cycles).
- Linear models (ΔE = α·d + β·v²·d) for baseline comparisons.
- ML-based models trained on fleet data.
- Probabilistic models (energy as a distribution rather than a point estimate).

All extensions plug in through the same `EnergyModel` Protocol without
changing the vehicle entity or routing algorithms.

Current implementations
-----------------------
- `FioriEnergyModel`: Physics-based model following Fiori et al. (2016).
  **Equations are not yet implemented.** This is a stub that declares method
  signatures and parameter requirements. Implementation proceeds only after
  approval of a detailed technical design document.

Future implementations (not in Phase 3)
-----------------------------------------
- `PolynomialEnergyModel`: NREL polynomial regression.
- `LinearEnergyModel`: ΔE = α·d + β·v²·d baseline.
- `MLEnergyModel`: learned from fleet trace data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from e3hybrid.core.exceptions import VehicleError


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class EnergyModel(Protocol):
    """Interface that all energy consumption models must satisfy.

    Routing algorithms and simulation components depend only on this interface.
    They must never import a concrete energy model directly.

    Methods
    -------
    compute_energy_kwh(speed_mps, distance_m, acceleration_mps2, grade, ...):
        Return the energy consumed in kWh for traversing a road segment.
    """

    def compute_energy_kwh(
        self,
        speed_mps: float,
        distance_m: float,
        acceleration_mps2: float = 0.0,
        grade: float = 0.0,
        duration_s: float | None = None,
    ) -> float:
        """Compute energy consumed for a road-segment traversal.

        Parameters
        ----------
        speed_mps:
            Average or constant speed in metres per second during traversal.
        distance_m:
            Segment length in metres.
        acceleration_mps2:
            Average acceleration in metres per second squared. Positive =
            accelerating; negative = braking. Used for inertial force.
        grade:
            Road grade as a dimensionless slope (rise / run). Positive =
            uphill; negative = downhill. 0.0 = flat. Example: 5% grade = 0.05.
        duration_s:
            Traversal duration in seconds. If `None`, computed as
            `distance_m / speed_mps`. Used to account for auxiliary loads
            (HVAC, electronics) that consume power over time.

        Returns
        -------
        float:
            Energy consumed in kWh. Always non-negative. Negative values
            (from regenerative braking on downhill segments) are clamped to 0.

        Raises
        ------
        VehicleError:
            If inputs are invalid (negative speed, negative distance, …).
        """
        ...


# ---------------------------------------------------------------------------
# Fiori et al. (2016) physics-based model (stub — equations not implemented)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FioriEnergyModel:
    """Physics-based EV energy consumption model following Fiori et al. (2016).

    **This is a stub. The actual equations are not yet implemented.**
    Implementation proceeds only after approval of a detailed technical design
    document that specifies:

    1. Every equation being implemented.
    2. Every parameter and its source (SUMO, config, literature, simulation).
    3. Which parameters are configurable via YAML.
    4. Assumptions and simplifications.

    Parameter overview (for design doc — not yet used)
    ---------------------------------------------------
    vehicle_mass_kg:
        Total vehicle mass including payload, in kg. Affects inertia and
        rolling resistance.
    drag_coefficient:
        Dimensionless aerodynamic drag coefficient (Cd). Typical EV: 0.24–0.30.
    frontal_area_m2:
        Frontal cross-sectional area in m². Typical compact EV: 2.0–2.5 m².
    rolling_resistance_coeff:
        Dimensionless rolling resistance coefficient (Cr). Typical tyre on
        asphalt: 0.01–0.015.
    drivetrain_efficiency:
        Dimensionless motor + inverter efficiency (η). Typical EV: 0.85–0.92.
    regen_efficiency:
        Dimensionless regenerative braking efficiency (η_regen). Captures
        motor-as-generator efficiency and battery charge acceptance. Typical:
        0.6–0.7.
    auxiliary_power_w:
        Constant auxiliary load in watts (HVAC, electronics, lighting).
        Typical: 200–1000 W.
    air_density_kg_m3:
        Air density in kg/m³. Standard sea-level: 1.225 kg/m³. Can vary with
        altitude and temperature.
    gravity_m_s2:
        Gravitational acceleration in m/s². Standard: 9.81 m/s².

    All parameters must be positive. They are validated at construction.

    Future SUMO integration (design requirement)
    --------------------------------------------
    When the SUMO adapter is added (Phase 8), the following values must be
    supplied directly from TraCI calls **without changing this interface**:

    - `speed_mps` ← TraCI vehicle.getSpeed()
    - `acceleration_mps2` ← TraCI vehicle.getAcceleration()
    - `distance_m` ← edge length from DirectedGraph or TraCI edge.getLength()
    - `duration_s` ← simulation timestep or edge traversal time
    - `grade` ← (future) computed from SUMO edge elevation data when available

    The EnergyModel interface is designed so that these values can be passed
    in without the model knowing whether they came from SUMO, a synthetic
    scenario, or a replay trace.
    """

    vehicle_mass_kg: float
    drag_coefficient: float
    frontal_area_m2: float
    rolling_resistance_coeff: float
    drivetrain_efficiency: float
    regen_efficiency: float
    auxiliary_power_w: float
    air_density_kg_m3: float = 1.225
    gravity_m_s2: float = 9.81

    def __post_init__(self) -> None:
        """Validate energy model parameters."""

        if self.vehicle_mass_kg <= 0:
            raise VehicleError("vehicle_mass_kg must be positive")
        if self.drag_coefficient <= 0:
            raise VehicleError("drag_coefficient must be positive")
        if self.frontal_area_m2 <= 0:
            raise VehicleError("frontal_area_m2 must be positive")
        if self.rolling_resistance_coeff <= 0:
            raise VehicleError("rolling_resistance_coeff must be positive")
        if not (0 < self.drivetrain_efficiency <= 1):
            raise VehicleError("drivetrain_efficiency must be in (0, 1]")
        if not (0 < self.regen_efficiency <= 1):
            raise VehicleError("regen_efficiency must be in (0, 1]")
        if self.auxiliary_power_w < 0:
            raise VehicleError("auxiliary_power_w must be non-negative")
        if self.air_density_kg_m3 <= 0:
            raise VehicleError("air_density_kg_m3 must be positive")
        if self.gravity_m_s2 <= 0:
            raise VehicleError("gravity_m_s2 must be positive")

    # ------------------------------------------------------------------
    # Protocol method
    # ------------------------------------------------------------------

    def compute_energy_kwh(
        self,
        speed_mps: float,
        distance_m: float,
        acceleration_mps2: float = 0.0,
        grade: float = 0.0,
        duration_s: float | None = None,
    ) -> float:
        """Compute energy consumed for a road-segment traversal.

        **NOT YET IMPLEMENTED.**

        The implementation will follow the force-balance equation from Fiori
        et al. (2016):

            P_traction = (F_inertia + F_grade + F_rolling + F_aero) · v / η

        where:
            F_inertia = m · a
            F_grade   = m · g · sin(arctan(grade))  ≈  m · g · grade  for small grades
            F_rolling = m · g · Cr · cos(arctan(grade))  ≈  m · g · Cr
            F_aero    = 0.5 · ρ · Cd · A · v²

        Energy over the segment:
            E_traction = P_traction · t_duration

        Regenerative braking (when P_traction < 0):
            E_recovered = -P_traction · η_regen · t_duration

        Auxiliary load:
            E_aux = P_aux · t_duration

        Total:
            E_total = max(0, E_traction + E_aux)

        Detailed equations, parameter sources, and validation will be
        documented in a separate technical design document before
        implementation proceeds.

        Parameters
        ----------
        speed_mps:
            Average or constant speed in m/s.
        distance_m:
            Segment length in metres.
        acceleration_mps2:
            Average acceleration in m/s². Positive = accelerating; negative =
            braking.
        grade:
            Road grade (rise / run). Positive = uphill; negative = downhill.
        duration_s:
            Traversal duration in seconds. If `None`, computed as
            `distance_m / speed_mps`.

        Returns
        -------
        float:
            Energy consumed in kWh. Always non-negative.

        Raises
        ------
        VehicleError:
            If inputs are invalid (negative speed, negative distance, …).
        NotImplementedError:
            Always raised in Phase 3 Stage 1 — equations not yet implemented.
        """

        # Input validation (will remain after implementation).
        if speed_mps < 0:
            raise VehicleError("speed_mps must be non-negative")
        if distance_m < 0:
            raise VehicleError("distance_m must be non-negative")
        if duration_s is not None and duration_s < 0:
            raise VehicleError("duration_s must be non-negative when provided")

        # Phase 3 Stage 1: stub only.
        raise NotImplementedError(
            "FioriEnergyModel.compute_energy_kwh is not yet implemented. "
            "Implementation proceeds only after approval of a detailed "
            "technical design document specifying equations, parameters, "
            "and their sources."
        )
