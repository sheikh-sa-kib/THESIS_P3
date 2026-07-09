# Energy Model Design Document

**Document Status:** Phase 3 Stage 2 — awaiting approval before implementation  
**Model:** Physics-based electric vehicle energy consumption (Fiori et al., 2016)  
**Date:** 2026-07-08  
**Approval Required Before:** Implementation of `FioriEnergyModel.compute_energy_kwh()`

---

## 1. Literature Reference

### Primary Source

**Fiori, C., Ahn, K., & Rakha, H. A. (2016).**  
*Power-based electric vehicle energy consumption model: Model development and validation.*  
Applied Energy, 168, 257–268.  
https://doi.org/10.1016/j.apenergy.2016.01.097

### Why This Model?

This thesis requires an energy consumption model that is:
- **Physics-based and interpretable** — every term corresponds to a real force or power component, making the model auditable for thesis defense.
- **Validated against real EVs** — the paper reports validation using Nissan Leaf, Mitsubishi i-MiEV, and Smart ED vehicles over EPA drive cycles.
- **Suitable for routing research** — the model has been adopted in multiple EV routing papers because it captures the speed-dependent nonlinearity of aerodynamic drag and the benefit of regenerative braking on downhill/deceleration segments.
- **Computationally efficient** — closed-form algebraic expression; O(1) per edge traversal.

### Comparison with Alternatives

| Model Type               | Advantages                          | Disadvantages for this thesis                |
|--------------------------|-------------------------------------|----------------------------------------------|
| **Linear (ΔE = α·d + β·v²·d)** | Simple; fast                        | Requires pre-calibration per speed regime; no explicit physics; no regenerative braking |
| **Polynomial (NREL)**    | EPA-validated; empirical fit        | Black-box regression; parameters not interpretable; harder to justify coefficient sources |
| **Machine Learning**     | Can capture complex interactions    | Requires large training dataset; not explainable; risk of overfitting; not acceptable for undergraduate thesis without extensive validation |
| **Fiori (physics-based)**| Transparent; validated; widely used | Requires more parameters than linear models (but all have clear physical meaning) |

**Decision:** Fiori best fits the research goals. The thesis focus is routing and swarm coordination under emergencies, not battery chemistry or energy modeling innovation. Using a well-established, validated model reduces the risk of fabricated results and allows the thesis to concentrate on the routing contribution.

---

## 2. Mathematical Formulation

### 2.1 Force Balance Equation

The instantaneous traction power required to move the vehicle is:

```
P_traction(t) = [F_inertia(t) + F_grade(t) + F_rolling(t) + F_aero(t)] · v(t) / η_drivetrain
```

**Units:** Watts (W)  
**Purpose:** Compute the mechanical power demand at the wheels, accounting for all resistive and propulsive forces.  
**Assumption:** Drivetrain efficiency η is constant (motor and inverter losses are load-independent). This is a simplification; real EVs have efficiency maps. However, Fiori et al. validate this approximation as acceptable for route-level energy estimation.


### 2.2 Force Components

#### F_inertia — Inertial force (acceleration/deceleration)

```
F_inertia(t) = m · a(t)
```

**Units:** Newtons (N)  
**Purpose:** Capture the force required to accelerate the vehicle's mass.  
**Note:** When a(t) < 0 (braking), F_inertia < 0, contributing to negative traction power (energy recovery opportunity).

#### F_grade — Gravitational force due to road slope

```
F_grade(t) = m · g · sin(θ(t))
```

**Approximation for small grades (|θ| < 10°):**

```
F_grade(t) ≈ m · g · grade(t)
```

where `grade(t) = rise / run` (dimensionless slope).

**Units:** Newtons (N)  
**Purpose:** Account for uphill resistance (positive) or downhill assistance (negative).  
**Assumption (Phase 3):** All road segments are flat (grade = 0). Grade will be computed from SUMO elevation data in Phase 8 when the SUMO adapter is added. The model is designed to accept grade as an input so that no code changes are required later.

#### F_rolling — Rolling resistance

```
F_rolling(t) = m · g · C_r · cos(θ(t))
```

**Approximation for small grades:**

```
F_rolling(t) ≈ m · g · C_r
```

**Units:** Newtons (N)  
**Purpose:** Model tyre deformation and friction losses. C_r depends on tyre type, road surface, and inflation pressure.  
**Assumption:** C_r is constant (no temperature, wear, or surface-type variation). Extensions can parameterise C_r per edge type (asphalt, gravel, wet road).


#### F_aero — Aerodynamic drag force

```
F_aero(t) = (1/2) · ρ · C_d · A_f · v(t)²
```

**Units:** Newtons (N)  
**Purpose:** Model air resistance, which scales with the square of speed. This term dominates at highway speeds and is the key reason a physics-based model is superior to a linear approximation.  
**Assumption:** Wind speed is zero (vehicle moves through still air). Headwind or tailwind can be added later as a velocity offset without changing the interface.

### 2.3 Total Traction Power

Substituting the force components:

```
P_traction(t) = [m·a(t) + m·g·grade(t) + m·g·C_r + (1/2)·ρ·C_d·A_f·v(t)²] · v(t) / η_drivetrain
```

**When P_traction(t) > 0:** Motor draws energy from battery (propulsion).  
**When P_traction(t) < 0:** Kinetic energy is available for recovery (braking).

### 2.4 Regenerative Braking

When P_traction(t) < 0 (vehicle is braking or coasting downhill):

```
P_recovered(t) = |P_traction(t)| · η_regen
```

**Units:** Watts (W)  
**Purpose:** Capture energy returned to the battery during braking. η_regen accounts for motor-as-generator efficiency and battery charge acceptance.  
**Assumption:** Regenerative braking is only active when P_traction < 0. No friction/regeneration split model is included (the vehicle always maximises regenerative braking up to the motor's physical limit). This is consistent with Fiori et al.

### 2.5 Auxiliary Power Load

```
P_aux = constant (W)
```

**Units:** Watts (W)  
**Purpose:** Model constant electrical loads: HVAC, headlights, on-board electronics, instrument cluster.  
**Assumption:** P_aux is constant and independent of speed, temperature, or time of day. Dynamic auxiliary load (e.g., HVAC ramping with temperature) is excluded from Phase 3 scope.


### 2.6 Energy Consumption Over a Road Segment

For a road segment traversed at constant or average speed `v_avg` over duration `Δt`:

**Case 1: Propulsion (P_traction ≥ 0)**

```
E_segment = (P_traction + P_aux) · Δt   (kWh)
```

Convert watts to kilowatts and seconds to hours:

```
E_segment = (P_traction + P_aux) · Δt / 3600000   (kWh)
```

**Case 2: Regenerative braking (P_traction < 0)**

```
E_segment = max(0, P_aux · Δt - |P_traction| · η_regen · Δt) / 3600000   (kWh)
```

**Purpose:** Ensure that when regenerative braking recovers more energy than auxiliary loads consume, the net energy is zero (battery cannot gain energy beyond what was consumed previously). The `max(0, ...)` clamp prevents perpetual motion.

**Duration Δt:**

If not provided explicitly, compute from distance and speed:

```
Δt = distance / v_avg   (seconds)
```

**Assumption:** Speed and acceleration are constant over the segment. For fine-grained simulations, SUMO can provide per-timestep speed and acceleration via TraCI; the model accepts these as inputs.

---

## 3. Parameter Inventory

| Parameter                | Meaning                                      | Units       | Source              | Configurable (YAML) | Expected Provider        |
|--------------------------|----------------------------------------------|-------------|---------------------|---------------------|--------------------------|
| `m`                      | Vehicle mass (including payload)             | kg          | Configuration       | Yes                 | `vehicle_mass_kg`        |
| `g`                      | Gravitational acceleration                   | m/s²        | Constant (9.81)     | Yes (optional)      | `gravity_m_s2`           |
| `C_r`                    | Rolling resistance coefficient               | —           | Configuration       | Yes                 | `rolling_resistance_coeff` |
| `C_d`                    | Aerodynamic drag coefficient                 | —           | Configuration       | Yes                 | `drag_coefficient`       |
| `A_f`                    | Frontal cross-sectional area                 | m²          | Configuration       | Yes                 | `frontal_area_m2`        |
| `ρ`                      | Air density                                  | kg/m³       | Constant (1.225)    | Yes (optional)      | `air_density_kg_m3`      |
| `η_drivetrain`           | Drivetrain efficiency (motor + inverter)     | —           | Configuration       | Yes                 | `drivetrain_efficiency`  |
| `η_regen`                | Regenerative braking efficiency              | —           | Configuration       | Yes                 | `regen_efficiency`       |
| `P_aux`                  | Auxiliary power load (HVAC, lights, etc.)    | W           | Configuration       | Yes                 | `auxiliary_power_w`      |
| `v(t)`                   | Vehicle speed at time t                      | m/s         | Simulation / SUMO   | No                  | Passed as function arg   |
| `a(t)`                   | Vehicle acceleration at time t               | m/s²        | Simulation / SUMO   | No                  | Passed as function arg   |
| `grade(t)`               | Road slope (rise / run)                      | —           | DirectedGraph / SUMO| No                  | Passed as function arg (Phase 8) |
| `distance`               | Segment length                               | m           | DirectedGraph       | No                  | `Edge.length_m`          |
| `Δt`                     | Traversal duration                           | s           | Simulation / computed | No                | Passed as function arg or computed |


---

## 4. Data Source Mapping

### Configuration-provided (YAML → `VehicleFactory` → `FioriEnergyModel` constructor)

- `vehicle_mass_kg`: From vehicle configuration. Typical compact EV: 1400–1600 kg.
- `drag_coefficient`: From manufacturer spec or literature. Typical EV: 0.24–0.30.
- `frontal_area_m2`: From manufacturer spec or estimated from vehicle class. Typical compact: 2.0–2.5 m².
- `rolling_resistance_coeff`: From literature. Typical low-rolling-resistance tyre on dry asphalt: 0.008–0.012.
- `drivetrain_efficiency`: From literature. Typical EV: 0.85–0.92 (motor 90–95%, inverter 95–98%, combined).
- `regen_efficiency`: From literature. Typical: 0.60–0.70 (accounts for motor reverse operation, battery charging losses, and control strategy conservatism).
- `auxiliary_power_w`: From literature or estimated. Typical: 200–1000 W depending on season and comfort settings.
- `air_density_kg_m3`: Optional override. Standard sea-level: 1.225 kg/m³. Can vary with altitude (Denver: ~1.05 kg/m³).
- `gravity_m_s2`: Optional override. Standard: 9.81 m/s². Typically not changed unless simulating other planets (out of scope).

### Simulation-provided (passed as function arguments to `compute_energy_kwh`)

- `speed_mps`: From `Edge.effective_speed_mps`, or from SUMO `vehicle.getSpeed()` in Phase 8.
- `distance_m`: From `Edge.length_m`.
- `acceleration_mps2`: From SUMO `vehicle.getAcceleration()` in Phase 8. For Phase 3–7 (pre-SUMO), set to 0.0 (constant-speed assumption).
- `grade`: From `Edge` metadata (future Phase 4 when elevation is imported), or from SUMO edge elevation in Phase 8. For Phase 3, set to 0.0 (flat roads).
- `duration_s`: Optional. If `None`, computed as `distance_m / speed_mps`. Can be explicitly provided by the simulator when timesteps are irregular.

### Literature-provided (constants, optionally overridden in YAML)

- `ρ` (air_density_kg_m3): 1.225 kg/m³ (ISO 2533 standard atmosphere at sea level, 15°C).
- `g` (gravity_m_s2): 9.80665 m/s² (standard gravity; rounded to 9.81 in practice).

### Future Extensions (not in Phase 3)

- `grade`: Computed from edge start/end elevations when graph imports SUMO `.net.xml` with elevation data (Phase 4) or queried via TraCI (Phase 8).
- `C_r`: Could become edge-type-dependent (asphalt 0.010, gravel 0.015, wet 0.012) in future scenario variations.
- Temperature-dependent `ρ` and battery efficiency: `TemperatureAwareBattery` implementation (future research).

---

## 5. YAML Configuration

### Example Vehicle Configuration

```yaml
vehicle:
  battery:
    capacity_kwh: 40.0
    initial_soc_kwh: 32.0  # 80% initial charge

  constraints:
    min_soc_kwh: 4.0       # 10% minimum (preserve battery health)
    max_soc_kwh: 40.0
    max_speed_mps: 33.3    # ~120 km/h
    max_payload_kg: 200.0

  energy_model:
    type: fiori

    # Vehicle physical parameters
    vehicle_mass_kg: 1520.0         # Nissan Leaf curb weight + driver
    drag_coefficient: 0.28          # Nissan Leaf Cd
    frontal_area_m2: 2.19           # Nissan Leaf frontal area
    rolling_resistance_coeff: 0.010 # Low-RR tyre on dry asphalt

    # Efficiency parameters
    drivetrain_efficiency: 0.90     # Motor + inverter combined
    regen_efficiency: 0.65          # Regenerative braking recovery rate

    # Auxiliary load
    auxiliary_power_w: 500.0        # HVAC, lights, electronics

    # Optional environment overrides
    # air_density_kg_m3: 1.225      # Sea level (default)
    # gravity_m_s2: 9.81            # Standard (default)

  metadata:
    vehicle_class: compact
    manufacturer: Nissan
    model: Leaf
```

**No hardcoded numerical values in the implementation.** All vehicle-specific parameters come from this configuration. Different vehicle types (compact, sedan, SUV, van) use different config files with manufacturer-sourced or literature-sourced parameters.


---

## 6. Computational Analysis

### Time Complexity

**Per edge traversal:**  
O(1) — closed-form algebraic expression. No loops, recursion, or iterative solvers.

**Steps:**
1. Compute four force components: O(1) arithmetic each → O(4) = O(1)
2. Sum forces and multiply by velocity: O(1)
3. Divide by efficiency: O(1)
4. Check sign and apply regenerative braking logic: O(1)
5. Add auxiliary power: O(1)
6. Multiply by duration and convert units: O(1)

**Total per edge:** ~15–20 floating-point operations.

### Space Complexity

**Per vehicle:**  
O(1) — the `FioriEnergyModel` stores 9 scalar parameters (mass, Cd, A_f, C_r, η_drivetrain, η_regen, P_aux, ρ, g). No dynamic allocation during energy computation.

**Total for N vehicles:**  
O(N) — each vehicle holds one `FioriEnergyModel` instance.

### Execution Frequency

**Routing phase (pre-simulation):**  
Energy is computed for **every candidate edge in every candidate route** generated by the routing algorithm. For a graph with E edges and R candidate routes per vehicle:
- Dijkstra: O(E log V) edge relaxations per vehicle
- A*: O(E log V) with heuristic pruning
- ACO/BCO/PSO: 10–100× edge evaluations per iteration

**Simulation phase (Phase 5+):**  
Energy is computed **once per edge traversal per vehicle**. For a 1-hour simulation with 1000 vehicles, each traversing 10–50 edges:
- Total energy computations: 10,000–50,000 per hour
- At 60 ticks/minute: ~3–10 computations per tick per vehicle

### Suitability for Large Simulations

At ~20 FLOPs per energy computation:
- 50,000 computations/hour = 1,000,000 FLOPs/hour ≈ 278 FLOPs/second
- Modern CPU: 10–100 GFLOPS → energy model is **< 0.001% of CPU budget**

**Bottleneck will be:**
- Graph traversal (Dijkstra/A*: O(E log V))
- Swarm communication (ACO pheromone updates, PSO particle broadcast)
- SUMO TraCI synchronisation (network I/O)

**Conclusion:** The Fiori model is computationally negligible. Optimisation effort should focus on routing algorithm efficiency, not energy model micro-optimisation.


---

## 7. Validation Strategy

### Unit Tests (Immediate — Phase 3)

1. **Parameter validation**  
   - Reject negative mass, Cd, A_f, C_r.
   - Reject efficiencies outside (0, 1].
   - Reject negative auxiliary power.

2. **Input validation**  
   - Reject negative speed.
   - Reject negative distance.
   - Reject negative duration when provided.

3. **Zero-speed edge case**  
   - When `speed_mps = 0` and `distance_m > 0`, duration must be explicitly provided (otherwise division by zero).
   - Energy should be `P_aux · Δt` (vehicle is stationary but auxiliary load persists).

4. **Constant-speed, flat-road baseline**  
   - For known inputs (e.g., 15 m/s, 1000 m, flat, no acceleration), hand-compute expected energy and assert match within floating-point tolerance.

5. **Regenerative braking sanity check**  
   - When `a < 0` (braking), energy consumed should be less than for `a = 0` (coasting at same average speed).
   - When `grade < 0` (downhill), energy should be less than flat.

6. **Energy conservation**  
   - Sum of energy over a closed loop (up and down a hill) should be positive (losses exceed recovery due to η_regen < 1 and auxiliary loads).

7. **Boundary conditions**  
   - Very low speed (0.1 m/s): aerodynamic drag negligible, rolling resistance dominates.
   - Very high speed (50 m/s): aerodynamic drag dominates.


### Integration Tests (Phase 5 — Simulation)

1. **Battery depletion under constant driving**  
   - Vehicle traverses edges at constant speed until SoC reaches minimum threshold.
   - Total energy consumed should equal `(initial_soc - min_soc)`.

2. **Regenerative braking on downhill segment**  
   - Vehicle descends a grade → energy consumed should be negative or very low.
   - Battery SoC after descent should be higher than or equal to SoC before descent (minus auxiliary consumption).

3. **Comparison with literature values**  
   - Fiori et al. (2016) report energy consumption for Nissan Leaf over EPA Urban Dynamometer Driving Schedule (UDDS).
   - Replicate UDDS speed profile in a synthetic scenario → compare computed energy with paper's reported values (within 5–10% tolerance is acceptable due to auxiliary load and temperature differences).

### Sanity Checks (Runtime — every energy computation)

1. **Non-negative energy**  
   - `compute_energy_kwh` must never return a value < 0. The `max(0, ...)` clamp ensures this.

2. **Physics plausibility**  
   - Energy consumed at 30 m/s should be > energy at 15 m/s for the same distance (higher speed → higher drag).
   - Energy consumed uphill should be > energy on flat road.

3. **Battery overdischarge prevention**  
   - `ElectricVehicle.traverse_edge` must call `battery.can_discharge(energy_kwh)` before updating state.
   - If battery cannot discharge the computed energy, raise `VehicleError` and halt the vehicle.

### Validation Against Real EV Data (Future — beyond Phase 3 scope)

- Collect GPS + SoC traces from a real Nissan Leaf or similar EV.
- Replay the trace through the simulator with matching vehicle parameters.
- Compare predicted final SoC with actual final SoC.
- This is outside the undergraduate scope but would strengthen the thesis if data becomes available.

---

## 8. Limitations

The following effects are **intentionally excluded** from the Phase 3 implementation to keep the undergraduate thesis scope manageable:

### Excluded: Battery Aging and Degradation

- **What:** Battery capacity fade and internal resistance increase over charge cycles.
- **Why excluded:** Modelling degradation requires tracking cumulative energy throughput, temperature history, and depth-of-discharge distributions. This is a research topic in itself.
- **Impact:** The model assumes battery capacity remains constant. For short-term simulations (hours to days), this is acceptable. For long-term fleet studies (months to years), a `DegradationBattery` implementation would be needed.

### Excluded: Temperature Effects

- **What:** Battery efficiency, motor efficiency, and auxiliary power consumption all vary with ambient and battery temperature.
- **Why excluded:** Requires thermal modelling of the battery pack and cabin, HVAC power modelling as a function of temperature, and temperature-dependent efficiency curves.
- **Impact:** The model assumes constant efficiency regardless of weather. In reality, cold weather reduces range by 20–40%. A `TemperatureAwareBattery` and dynamic `P_aux(T)` would address this in future work.


### Excluded: Wind Speed

- **What:** Headwind increases effective aerodynamic drag; tailwind decreases it.
- **Why excluded:** Requires wind field data (speed, direction) for every road segment, which is not typically available in SUMO scenarios.
- **Impact:** Model assumes still air. Real-world wind can increase/decrease energy by 5–15%. Future extension: parameterise wind as a velocity offset in the aerodynamic drag term.

### Excluded: Road Surface Variations

- **What:** Rolling resistance depends on surface type (asphalt, concrete, gravel, wet, snow).
- **Why excluded:** SUMO road networks do not include surface-type metadata by default.
- **Impact:** Model assumes constant `C_r`. Future extension: assign `C_r` per edge type in `Edge.metadata` and pass to energy model.

### Excluded: Tyre Pressure and Wear

- **What:** Under-inflated or worn tyres increase rolling resistance.
- **Why excluded:** Real-time tyre condition is not tracked in typical simulations.
- **Impact:** Model assumes optimal tyre condition. Real-world `C_r` can increase by 20–50% with poor maintenance.

### Excluded: Motor Thermal Limits

- **What:** Sustained high power (e.g., climbing a long grade at high speed) can trigger motor derating to prevent overheating.
- **Why excluded:** Requires thermal model of motor, inverter, and cooling system.
- **Impact:** Model assumes motor can sustain full power indefinitely. Real EVs may reduce power after 2–5 minutes of sustained hill climbing.

### Excluded: Charging Behaviour

- **What:** Time to charge, charging station availability, charging power as a function of SoC (taper at high SoC).
- **Why excluded:** Charging station logic is planned for Phase 6 (after routing and simulation are stable).
- **Impact:** Phase 3 vehicles can travel until SoC reaches minimum threshold, then are stranded. Charging will be added once routing algorithms can plan for charging stops.

### Excluded: C-rate Battery Losses

- **What:** High discharge rates (high power demand) reduce battery efficiency due to internal resistance heating.
- **Why excluded:** Would require a battery model with internal resistance and heat generation.
- **Impact:** Model assumes battery efficiency is constant regardless of discharge rate. Real batteries lose 5–10% efficiency at high C-rates.

**Justification:** These exclusions are standard in EV routing research. The Fiori model is already more detailed than most routing papers, which use linear energy approximations. Adding all excluded effects would shift the thesis focus from routing to battery/vehicle modelling, which is not the research goal.


---

## 9. Extension Strategy

The `EnergyModel` Protocol ensures that future enhancements can be added **without modifying the vehicle entity, routing algorithms, or simulation core**. Extensions are plugged in through the same interface.

### Temperature-Aware Energy Model (Future Research)

**Implementation:** `TemperatureAwareEnergyModel(FioriEnergyModel)`

**Additions:**
- Accept `ambient_temp_c: float` as an additional argument to `compute_energy_kwh`.
- Modify `η_drivetrain` and `η_regen` as functions of temperature (lookup table or piecewise-linear fit).
- Modify `P_aux` as a function of temperature (HVAC power increases below 15°C and above 25°C).
- Modify battery efficiency (via a `TemperatureAwareBattery` implementation).

**Data source:** Ambient temperature from SUMO weather plugin or scenario metadata.

**No changes required to:**
- `ElectricVehicle` entity
- `VehicleFactory` (just add temperature config keys)
- Routing algorithms (still call `energy_model.compute_energy_kwh(...)`)

### Weather-Aware Energy Model (Rain, Snow)

**Implementation:** `WeatherAwareEnergyModel(TemperatureAwareEnergyModel)`

**Additions:**
- Accept `weather_condition: str` (clear / rain / snow) as argument.
- Modify `C_r`: rain → +10%, snow → +30%.
- Modify `ρ`: slight increase in humid air (negligible effect).
- Modify `P_aux`: headlights, wipers, defroster → +100–300 W.

**Data source:** SUMO weather plugin or scenario time-of-day heuristic (night → headlights).


### Elevation-Aware Energy Model (Phase 8 — SUMO Integration)

**Implementation:** Modify `FioriEnergyModel` argument handling (no new class needed).

**Additions:**
- When SUMO provides edge elevation data, compute `grade = (elevation_end - elevation_start) / edge_length`.
- Pass `grade` to `compute_energy_kwh(grade=...)`.
- The existing force-balance equation already supports grade; no mathematical changes needed.

**Data source:** SUMO `.net.xml` elevation attributes, or TraCI edge queries.

**No changes required to:** Routing algorithms, vehicle entity, battery models.

### Battery Degradation Model (Future Research)

**Implementation:** `DegradationBattery(SimpleBattery)`

**Additions:**
- Track cumulative energy throughput (kWh cycled).
- Track equivalent full cycles (EFC).
- Apply capacity fade curve (e.g., 80% capacity after 1000 EFC).
- Reduce `capacity_kwh` over time.
- Increase internal resistance (reduce charging/discharging efficiency).

**Data source:** Battery aging curves from literature (e.g., Nissan Leaf degradation studies, NREL battery aging data).

**Interface compatibility:** `Battery` Protocol already includes `capacity_kwh` as a property, so routing algorithms automatically see reduced capacity.

### Multi-Class Vehicle Models (Future)

**Implementation:** Different YAML configs for each vehicle class.

| Vehicle Class | Mass (kg) | Cd   | A_f (m²) | C_r   | Battery (kWh) |
|---------------|-----------|------|----------|-------|---------------|
| Compact       | 1500      | 0.28 | 2.2      | 0.010 | 40            |
| Sedan         | 1800      | 0.25 | 2.4      | 0.010 | 60            |
| SUV           | 2200      | 0.32 | 2.8      | 0.012 | 75            |
| Van           | 2500      | 0.35 | 3.2      | 0.012 | 80            |

**Factory modification:** `VehicleFactory.create_from_config` already accepts arbitrary config dicts, so no code changes are needed. Just provide different config files.

### Machine Learning Energy Model (Future Research — Advanced)

**Implementation:** `MLEnergyModel` (satisfies `EnergyModel` Protocol)

**Training:**
- Collect real EV traces (GPS, speed, SoC) from fleet telematics.
- Train a regression model (random forest, neural network) to predict `ΔE` from `(v, a, distance, grade, temperature, ...)`.
- Serialize trained model and load at runtime.

**Advantages:**
- Can capture complex interactions (e.g., driver aggression, traffic patterns).
- Can adapt to specific vehicle make/model without knowing physics parameters.

**Disadvantages:**
- Black-box; not interpretable for thesis defense.
- Requires large training dataset.
- Risk of overfitting or poor generalisation.

**Protocol compatibility:** `MLEnergyModel` implements `compute_energy_kwh(...)` just like `FioriEnergyModel`. Routing algorithms and simulation core are unchanged.


---

## 10. Implementation Plan

### Phase 3 Stage 2 (This Document — Awaiting Approval)

- Document mathematical formulation.
- Document parameter sources and configuration.
- Document validation strategy.
- **Stop. Wait for approval before proceeding.**

### Phase 3 Stage 3 (After Approval)

- Implement `FioriEnergyModel.compute_energy_kwh()` following equations in Section 2.
- Add inline code comments referencing equation numbers from Fiori et al. (2016).
- Add validation unit tests (Section 7).
- Run full test suite to ensure no regressions.

### Phase 3 Stage 4 (Integration Verification)

- Create example vehicle configs for Nissan Leaf, Tesla Model 3, Chevrolet Bolt.
- Use `VehicleFactory` to instantiate vehicles with different parameters.
- Compute energy for standard test cases (constant speed, acceleration, deceleration, grade).
- Compare results with hand calculations and literature values.

### Phase 4+ (Future Phases)

- Add elevation data to `DirectedGraph` from SUMO import.
- Pass `grade` to energy model when available.
- Integrate with routing algorithms (Dijkstra energy-aware variant).
- Add charging station logic.

---

## 11. Code Comment Strategy

Every equation implemented in `FioriEnergyModel.compute_energy_kwh()` will include an inline comment referencing the corresponding equation from the design document and/or Fiori et al. (2016).

**Example:**

```python
# Eq. 2.2.1: Inertial force — F_inertia = m · a
f_inertia = self.vehicle_mass_kg * acceleration_mps2

# Eq. 2.2.2: Gravitational force — F_grade ≈ m · g · grade (small angle approx)
f_grade = self.vehicle_mass_kg * self.gravity_m_s2 * grade

# Eq. 2.2.3: Rolling resistance — F_rolling ≈ m · g · C_r
f_rolling = (
    self.vehicle_mass_kg
    * self.gravity_m_s2
    * self.rolling_resistance_coeff
)

# Eq. 2.2.4: Aerodynamic drag — F_aero = (1/2) · ρ · C_d · A_f · v²
f_aero = (
    0.5
    * self.air_density_kg_m3
    * self.drag_coefficient
    * self.frontal_area_m2
    * speed_mps**2
)

# Eq. 2.3: Total traction power — P_traction = Σ(F) · v / η_drivetrain
total_force = f_inertia + f_grade + f_rolling + f_aero
p_traction = total_force * speed_mps / self.drivetrain_efficiency
```

This traceability ensures that every line of code can be defended during thesis review by pointing back to the design document and the published paper.


---

## 12. Research Milestone Policy

This document establishes the research milestone policy for all future phases of the E3-Hybrid framework. Each milestone listed below requires **explicit approval** before implementation proceeds.

| Milestone                        | Trigger                                             | Status                     |
|----------------------------------|-----------------------------------------------------|----------------------------|
| **Architecture milestone**       | New module, interface, or entity introduced         | Required before coding     |
| **Mathematical model milestone** | Physics equations, objective functions, cost formulas | Required before coding   |
| **Algorithm milestone**          | Dijkstra, A*, ACO, BCO, PSO, E3-Hybrid logic        | Required before coding     |
| **SUMO integration milestone**   | TraCI calls, SUMO adapter, edge import              | Required before coding     |
| **Experiment framework milestone** | Experiment runner, output folder, metrics         | Required before coding     |
| **Final evaluation milestone**   | Comparative experiments, thesis results             | Required before reporting  |

**Rationale:** This prevents baking in design decisions that are hard to change later. Architecture decisions (interface shapes, data flow, module boundaries) are always harder to reverse than implementation details. Each milestone approval produces a reviewed design document that can be adapted directly into the corresponding thesis chapter.

---

*Document complete. Awaiting approval before implementing equations.*
