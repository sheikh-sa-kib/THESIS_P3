# Final Experiment Reproduction Guide

**Project:** E3-Hybrid — Decentralized Swarm Routing for Electric Vehicles Under Dynamic Urban Emergencies  
**SUMO Version:** 1.27.1  
**Python Version:** >=3.12  
**Last Updated:** 2026-07-09

---

## Table of Contents

1. [Repository Setup](#1-repository-setup)
2. [Required Software Versions](#2-required-software-versions)
3. [SUMO 1.27.1 Installation](#3-sumo-1271-installation)
4. [Python Environment Creation](#4-python-environment-creation)
5. [Required Folders](#5-required-folders)
6. [Network File Placement](#6-network-file-placement)
7. [Route Generation](#7-route-generation)
8. [Configuration Options](#8-configuration-options)
9. [Running Headless Simulations](#9-running-headless-simulations)
10. [Progress Reporting During Long Simulations](#10-progress-reporting-during-long-simulations)
11. [Running Validation Experiments](#11-running-validation-experiments)
12. [Running Benchmark Experiments](#12-running-benchmark-experiments)
13. [Running Deterministic Replay Tests](#13-running-deterministic-replay-tests)
14. [Running Emergency Simulations](#14-running-emergency-simulations)
15. [Running Congestion Experiments](#15-running-congestion-experiments)
16. [Running All Six Algorithms Individually](#16-running-all-six-algorithms-individually)
17. [Running Comparative Experiments](#17-running-comparative-experiments)
18. [Output Directory Structure](#18-output-directory-structure)
19. [CSV Outputs](#19-csv-outputs)
20. [Plot Outputs](#20-plot-outputs)
21. [Statistical Outputs](#21-statistical-outputs)
22. [Reproducing Every Figure Used in the Thesis](#22-reproducing-every-figure-used-in-the-thesis)
23. [Hardware Recommendations](#23-hardware-recommendations)
24. [Estimated Runtime on Low-End and High-End Machines](#24-estimated-runtime-on-low-end-and-high-end-machines)
25. [Troubleshooting Guide](#25-troubleshooting-guide)
26. [Common SUMO Errors](#26-common-sumo-errors)
27. [Expected Outputs for Successful Runs](#27-expected-outputs-for-successful-runs)
28. [GitHub Workflow (Clone to Reproduce)](#28-github-workflow-clone-to-reproduce)

---

## 1. Repository Setup

```bash
git clone <repository-url> e3hybrid
cd e3hybrid
```

The repository root contains:

| Path | Purpose |
|------|---------|
| `src/e3hybrid/` | Python package with 12 modules |
| `scripts/` | Experiment and validation runners |
| `data/maps/` | SUMO network file (immutable) |
| `data/routes/` | Pre-generated route file |
| `data/configs/` | SUMO configuration files |
| `docs/` | All thesis documentation |
| `tests/` | Unit, integration, acceptance, benchmark tests |
| `outputs/` | Experiment and validation outputs (gitignored) |
| `.venv/` | Virtual environment (gitignored, created locally) |

---

## 2. Required Software Versions

| Component | Version | Notes |
|-----------|---------|-------|
| Python | >=3.12 | Required for `e3hybrid` package syntax |
| SUMO | 1.27.1 | Exact version required for reproducibility |
| traci | >=1.20.0 | Python TraCI client (bundled with SUMO) |
| sumolib | >=1.20.0 | SUMO Python library (bundled with SUMO) |
| PyYAML | >=6.0.2 | Configuration serialisation |
| matplotlib | >=3.8 | Plotting (optional, for experiment plots) |
| psutil | >=5.9 | Memory tracking (optional) |
| pytest | >=8.0 | Test suite (optional, for verification) |

Cross-platform reproducibility is not guaranteed due to:
- Floating-point differences across CPU architectures
- SUMO behavioural differences between Windows and Linux
- Python dict iteration order (stable in >=3.7, but hash seed differs per process)

---

## 3. SUMO 1.27.1 Installation

### Windows

1. Download the SUMO 1.27.1 installer from https://sumo.dlr.de/docs/Downloads.php
2. Run the installer (default: `C:\Program Files\SUMO\`)
3. Add to environment variables:
   ```
   SUMO_HOME = C:\Program Files\SUMO
   ```
4. Add to `PATH`:
   ```
   C:\Program Files\SUMO\bin
   ```
5. Verify installation:
   ```bash
   sumo --version
   # Expected: SUMO 1.27.1
   ```

### Linux (Ubuntu/Debian)

```bash
# Add SUMO repository
sudo add-apt-repository ppa:sumo/stable
sudo apt-get update
sudo apt-get install sumo sumo-tools sumo-doc
# Verify
sumo --version
```

### macOS

```bash
brew install sumo
# Verify
sumo --version
```

### Verify SUMO_HOME is Discoverable

The project discovers SUMO at runtime via `SUMO_HOME` environment variable, falling back to `PATH`. Verify:

```bash
python -c "import os; print(os.environ.get('SUMO_HOME', 'NOT SET'))"
# Should print the SUMO installation path
```

---

## 4. Python Environment Creation

```bash
# Create virtual environment
python3.12 -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/macOS)
source .venv/bin/activate

# Install package in development mode
pip install -e ".[dev]"
```

This installs:
- `e3hybrid` package (editable, from `src/`)
- Runtime dependencies: `PyYAML`, `traci`, `sumolib`
- Dev dependencies: `pytest`, `pytest-cov`, `mypy`, `ruff`

Optional extras for experiment plots:
```bash
pip install matplotlib psutil
```

---

## 5. Required Folders

The project requires these directories to exist:

```
data/
  maps/          # Network files (.net.xml)
  routes/        # Route files (.rou.xml)
  configs/       # SUMO configuration (.sumocfg)
outputs/
  validation/    # Validation experiment outputs
  experiments/   # Full experiment outputs
  logs/          # Runtime logs
```

All directories are created automatically by the scripts. Verify with:

```bash
python -c "from pathlib import Path; p = Path('data'); assert (p/'maps').exists(); assert (p/'routes').exists(); assert (p/'configs').exists(); print('Data directories OK')"
```

---

## 6. Network File Placement

The SUMO road network file must be at:

```
data/maps/midtown_manhattan.net.xml
```

This file was generated from OpenStreetMap data using:

```bash
netconvert --osm-files manhattan.osm --output-file data/maps/midtown_manhattan.net.xml \
  --proj.utm --geometry.remove --roundabouts.guess \
  --tls.discard-simple --tls.join --tls.guess-signals \
  --ramps.guess --keep-edges.in-geo-boundary -74.000,40.745,-73.970,40.765 \
  --keep-edges.by-vclass passenger --remove-edges.isolated \
  --no-internal-links --junctions.join
```

Network properties:
- 715 nodes (after removing internal junctions)
- 1130 directed edges
- 53 nodes with out-degree 0 (dead-ends from internal-junction skipping)
- Schema version: 1.16
- Generated with SUMO 1.27.1

**This file must never be modified.** Any changes invalidate all prior experimental results.

---

## 7. Route Generation

The route file `data/routes/midtown_manhattan.rou.xml` is generated in two steps:

### Step 1 — Generate random trips:

```bash
python "%SUMO_HOME%/tools/randomTrips.py" \
  -n data/maps/midtown_manhattan.net.xml \
  -r data/routes/midtown_manhattan.rou.xml \
  --end 60.0 --period 2.0 --seed 42
```

### Step 2 — Compute shortest-path routes via duarouter:

```bash
duarouter -n data/maps/midtown_manhattan.net.xml \
  -s data/routes/midtown_manhattan.rou.xml.trips.xml \
  -o data/routes/midtown_manhattan.rou.xml \
  --routing-threads 2 --begin 0 --end 60.0
```

Parameters:
- **seed 42**: Reproducible trip generation
- **end 60.0**: 60 seconds of departures
- **period 2.0**: One vehicle every 2 seconds = 30 vehicles

The experiment runner also generates per-algorithm route files at runtime if needed.

---

## 8. Experiment Presets

The experiment is launched via `run_thesis.py` with a `--preset` argument:

```bash
python run_thesis.py --preset smoke     # installation verification
python run_thesis.py --preset light     # quick laptop comparison
python run_thesis.py --preset heavy     # thesis-quality (default)
python run_thesis.py --preset extreme   # stress-test
```

If no preset is specified, `heavy` is used.

### Preset Parameters

| Parameter | smoke | light | heavy | extreme |
|-----------|-------|-------|-------|---------|
| Steps | 30 | 100 | 300 | 600 |
| Vehicles | 10 | 50 | 300 | 500 |
| Departure period | 3.0 s | 2.0 s | 1.0 s | 1.0 s |
| Algorithms | dijkstra only | all 6 | all 6 | all 6 |
| Reroute interval | disabled | 10 steps | 10 steps | 10 steps |
| Emergencies | 0 | 0 | 3 | 5 |
| Offline benchmarks | no | yes | yes | yes |
| Auto plots | no | no | yes (34 figures) | yes |
| Expected runtime | ~10 s | ~5–15 min | ~30–90 min | ~2–6 hr |
| Target hardware | any | any laptop | desktop/server | 16 GB+ RAM, 8+ cores |

### Multi-Seed Runs

```bash
python run_thesis.py --preset heavy --seeds 42 43 44
```

Each seed produces a separate output directory. See `docs/PARAMETER_JUSTIFICATION.md`
for full parameter rationale.

---

## 9. Running the Complete Experiment

```bash
# Smoke test (verify installation, ~10 seconds)
python run_thesis.py --preset smoke

# Light comparison (all 6 algos, ~5–15 minutes)
python run_thesis.py --preset light

# Thesis-quality experiment (default, ~30–90 minutes)
python run_thesis.py --preset heavy

# Stress test (powerful hardware only, ~2–6 hours)
python run_thesis.py --preset extreme
```

Each preset automatically runs:
1. Environment preflight check
2. Pipeline validation (all 6 algorithms)
3. Online SUMO simulation with live per-step progress
4. Offline routing benchmarks
5. CSV generation (metrics, step-log, timing, emergency, routing)
6. Configuration snapshot + experiment manifest
7. Plot generation (34 publication-ready figures, `heavy` and `extreme` only)
8. Final comprehensive summary with all results

The `heavy` preset is the recommended one-command thesis experiment.

---

## 10. Running Validation Experiments

```bash
python scripts/run_validation.py
```

This validates:
| Check | What It Verifies |
|-------|-----------------|
| Route computation | Each algorithm can compute a route on the real network |
| Deterministic routing | Two identical calls produce identical routes |
| SUMO compatibility | Headless simulation runs without SUMO errors |
| Network integrity | Network loads and 300 steps execute cleanly |

Output: `outputs/validation/`

---

## 11. Deterministic Replay Tests

```bash
pytest tests/integration/test_determinism.py -v
```

---

## 12. Emergency Event Design

Emergencies are injected into the `heavy` and `extreme` presets via graph-state updates:

1. A deterministic schedule generates `N` events at random steps (seeded RNG)
2. Each event adds a 120 s emergency penalty to 3 random edges
3. The penalty is removed after 20 simulation steps
4. All routing algorithms see the same modified graph

This design ensures fair comparison — emergencies affect cost computation, not
algorithm-specific code paths.

---

## 13. Congestion Dynamics

Congestion emerges naturally from traffic density on the 715-node network:

| Density | Vehicle count | Period |
|---------|---------------|--------|
| Light | 30–60 | 5–10 s |
| Moderate | 60–200 | 2–5 s |
| Heavy | 200–500 | 0.5–2 s |
| Gridlock risk | >500 | — |

The `heavy` preset (300 vehicles, 1.0 s period) produces moderate congestion,
while `extreme` (500 vehicles) approaches gridlock.

Metrics collected per step: congestion edges (>80 % occupancy), blocked edges
(>95 %), average speed, teleport count, completed trips.

---

## 14. Experiment Design for Thesis Figures

| Experiment | Command | Purpose |
|------------|---------|---------|
| Baseline comparison | `--preset light` | All 6 algorithms, no emergencies |
| With emergencies | `--preset heavy` | Dynamic routing under emergencies |
| Multi-seed stats | `--preset heavy --seeds 42 43 44` | Statistical robustness |
| Scaling test | `--preset extreme` | Performance under high load |

---

## 18. Output Directory Structure

Each experiment run creates a timestamped directory:

```
outputs/experiments/
  run_YYYYMMDD_HHMMSS/
    config_snapshot.yaml         # Exact config used
    environment.json             # Python version, OS, packages, git commit
    git_commit.txt               # Commit hash or "unversioned"
    network_metadata.json        # Edge/junction counts
    metrics_summary.csv          # Per-algorithm aggregate metrics
    simulation_log.csv           # Per-step simulation data
    routing_log.csv              # Offline routing benchmark results
    plots/
      execution_time.png
      vehicles_over_time.png
      congestion_heatmap.png
      travel_time_comparison.png
      throughput.png
      memory_usage.png
```

The validation output is at:

```
outputs/validation/
  validation_summary.csv
  validation_metrics.json
  validation_plots.png
```

---

## 19. CSV Outputs

### `metrics_summary.csv`

| Column | Description |
|--------|-------------|
| `algorithm` | Algorithm name |
| `total_steps` | Steps simulated |
| `total_vehicles` | Vehicles generated |
| `total_reroutes` | Successful reroutes |
| `emergency_events` | Emergency events injected |
| `max_congestion_edges` | Peak edges >80% occupancy |
| `max_blocked_edges` | Peak edges >95% occupancy |
| `avg_travel_time_s` | Average edge travel time |
| `avg_speed_mps` | Average vehicle speed |
| `throughput` | Completed trips |
| `completed_trips` | Vehicles arrived |
| `failed_trips` | Vehicles failed | (always 0 in current implementation) |
| `teleport_count` | SUMO teleportation events |
| `avg_rerouting_latency_ms` | Average reroute compute time |
| `total_execution_s` | Wall-clock runtime |
| `peak_memory_mb` | Peak memory usage |

### `simulation_log.csv`

| Column | Description |
|--------|-------------|
| `algorithm` | Algorithm name |
| `step` | Simulation step |
| `active_vehicles` | Vehicles in network |
| `reroutes` | Cumulative reroutes |
| `emergency_events` | Active emergencies |
| `blocked_edges` | Edges >95% occupancy |
| `congestion_edges` | Edges >80% occupancy |
| `avg_speed_mps` | Mean vehicle speed |
| `completed_trips` | Cumulative completed |
| `failed_trips` | Cumulative failures |
| `teleport_count` | Cumulative teleports |

### `routing_log.csv`

| Column | Description |
|--------|-------------|
| `algorithm` | Algorithm name |
| `success_rate` | Fraction successful |
| `avg_runtime_s` | Mean compute time |
| `max_runtime_s` | Maximum compute time |
| `min_runtime_s` | Minimum compute time |
| `avg_distance_m` | Mean route distance |
| `successes` | Count successful |
| `failures` | Count failed |
| `total_requests` | Total routing requests |

---

## 20. Plot Outputs

The experiment runner generates 6 plot types:

### `plots/execution_time.png`
Bar chart of total wall-clock execution time per algorithm (seconds).

### `plots/vehicles_over_time.png`
Line chart of active vehicles per step, one line per algorithm.

### `plots/travel_time_comparison.png`
Bar chart of average edge travel time per algorithm (seconds).

### `plots/throughput.png`
Bar chart of completed trips per algorithm.

### `plots/memory_usage.png`
Bar chart of peak memory usage per algorithm (MB).

### `plots/congestion_heatmap.png`
Bar chart of peak congestion edges (>80% occupancy) per algorithm.

Generation requires `matplotlib`. If not installed, plots are skipped with:
```
[SKIP] matplotlib not installed; skipping plots
```

---

## 21. Statistical Outputs

### Aggregate Metrics (metrics_summary.csv)

Each algorithm produces aggregate metrics that can be compared directly:

| Metric | What It Captures |
|--------|-----------------|
| Throughput | How many vehicles completed their trip |
| Travel time | Average edge traversal time |
| Reroute latency | Algorithm compute time per reroute |
| Teleport count | How many vehicles were teleported (SUMO fallback) |
| Execution time | Total wall-clock runtime |

### Iteration-Level Statistics (Swarm Algorithms)

ACO, BCO, PSO, and E3-Hybrid produce `SwarmStatistics` containing:

| Field | Description |
|-------|-------------|
| `total_iterations` | Iterations completed |
| `total_runtime_s` | Algorithm wall-clock time |
| `best_score` | Best route cost found |
| `average_score` | Mean population cost |
| `worst_score` | Worst cost in population |
| `convergence_iteration` | Iteration where best converged |
| `candidate_count` | Routes evaluated |
| `solutions_evaluated` | Total evaluations |
| `diversity_history` | Population diversity over iterations |
| `score_history` | Best score over iterations |
| `termination_reason` | Why the algorithm stopped |

### Per-Iteration Statistics

Each swarm iteration records `IterationStatistics`:

| Field | Description |
|-------|-------------|
| `iteration` | Iteration number |
| `best_score` | Best cost this iteration |
| `average_score` | Mean population cost |
| `midrange_score` | (best + worst) / 2 |
| `worst_score` | Worst cost this iteration |
| `std_dev` | Population standard deviation |
| `diversity` | Population diversity measure |
| `best_solution_changed` | Whether best improved |
| `runtime_s` | Time for this iteration |

---

## 22. Reproducing Every Figure Used in the Thesis

### Figure 1: Route Computation Benchmark (Bar Chart)

```bash
python scripts/run_experiment.py --request-count 200 --timeout 60.0 --seed 42
```

Use `routing_log.csv` columns `avg_runtime_s` and `avg_distance_m`.

### Figure 2: Online Simulation Comparison (Multi-Panel)

```bash
python scripts/run_experiment.py --steps 300 --vehicles 300 --seed 42 \
  --algorithms dijkstra,astar,aco,bco,pso,e3hybrid
```

Use `simulation_log.csv` for time-series plots.  
Use `metrics_summary.csv` for aggregate bar charts.  
Plots are automatically generated in `plots/` directory.

### Figure 3: Emergency Response Analysis

```bash
# Baseline (no emergencies)
python scripts/run_experiment.py --emergency-count 0 --steps 300 --vehicles 200 \
  --algorithms dijkstra,aco,e3hybrid

# With emergencies
python scripts/run_experiment.py --emergency-count 5 --steps 300 --vehicles 200 \
  --algorithms dijkstra,aco,e3hybrid
```

Compare `teleport_count`, `avg_travel_time_s`, `throughput` between runs.

### Figure 4: Scalability Analysis

Run multiple times with increasing vehicle counts:

```bash
for veh in 50 100 200 300 400 500; do
  python scripts/run_experiment.py --vehicles $veh --steps 400 --seed 42 --period 0.8 \
    --algorithms dijkstra,aco,e3hybrid
done
```

Plot `total_execution_s` vs vehicle count per algorithm.

### Figure 5: Convergence Analysis (Swarm Algorithms)

Run offline routing:

```bash
python scripts/run_experiment.py --algorithms aco,bco,pso,e3hybrid \
  --request-count 50 --timeout 60.0 --seed 42
```

Use algorithm-internal `SwarmStatistics.score_history` and `diversity_history` for convergence plots.

---

## 23. Hardware Recommendations

### Minimum Requirements

| Component | Specification |
|-----------|---------------|
| CPU | 2 cores, 2.0 GHz |
| RAM | 8 GB |
| Disk | 500 MB free for outputs |
| OS | Windows 10/11, Ubuntu 20.04+, macOS 12+ |
| SUMO | 1.27.1 (see installation section) |

### Recommended Requirements

| Component | Specification |
|-----------|---------------|
| CPU | 4+ cores, 3.0 GHz |
| RAM | 16 GB |
| Disk | 5 GB free for multi-run experiments |
| OS | Ubuntu 22.04 (most reproducible) |

### Why These Requirements

- **SUMO simulation** is single-threaded but benefits from high clock speed (>3.0 GHz)
- **Swarm algorithm routing** (ACO, BCO, PSO, E3-Hybrid) uses 1 CPU core per algorithm call; multi-request benchmarks can benefit from higher clock speeds
- **Memory usage**: Each algorithm's internal state (pheromone matrices, route templates) scales with graph size. Manhattan network: ~60 MB peak per algorithm process
- **Disk**: CSVs and plots are small (<100 MB for a full 6-algorithm experiment)

---

## 24. Estimated Runtime on Low-End and High-End Machines

### Low-End Machine (2 cores, 2.0 GHz, 8 GB RAM)

| Experiment | Configuration | Estimated Time |
|------------|---------------|----------------|
| Validation | `run_validation.py` | 30–60 seconds |
| Single algorithm, small | `--vehicles 50 --steps 100` | 1–3 minutes |
| All 6 algorithms, standard | `--vehicles 300 --steps 300` | 15–30 minutes |
| All 6 with emergencies | `--emergency-count 5` | 15–30 minutes |
| Determinism tests | `pytest .../test_determinism.py` | 1–2 minutes |
| Acceptance tests | `pytest tests/acceptance/` | 5–10 minutes |
| Full test suite | `pytest` | 10–20 minutes |

### Mid-Range Machine (4 cores, 3.0 GHz, 16 GB RAM)

| Experiment | Estimated Time |
|------------|----------------|
| Validation | 15–30 seconds |
| Single algorithm, small | 30–90 seconds |
| All 6 algorithms, standard | 8–15 minutes |
| All 6 with emergencies | 8–15 minutes |
| Determinism tests | 30–60 seconds |
| Acceptance tests | 3–5 minutes |
| Full test suite | 5–10 minutes |

### High-End Machine (8+ cores, 4.0+ GHz, 32 GB RAM)

| Experiment | Estimated Time |
|------------|----------------|
| Validation | 10–20 seconds |
| Single algorithm, small | 20–40 seconds |
| All 6 algorithms, standard | 4–8 minutes |
| All 6 with emergencies | 4–8 minutes |
| Determinism tests | 20–30 seconds |
| Acceptance tests | 2–3 minutes |
| Full test suite | 3–5 minutes |

### Breakdown by Algorithm (Mid-Range Machine, 300 steps, 300 vehicles)

| Algorithm | Estimated Time | Notes |
|-----------|---------------|-------|
| Dijkstra | 2–4 minutes | Fast, deterministic |
| A* | 2–4 minutes | Similar to Dijkstra |
| ACO | 4–6 minutes | 100 iterations per reroute |
| BCO | 4–6 minutes | 50 iterations per reroute |
| PSO | 3–5 minutes | 50 iterations per reroute |
| E3-Hybrid | 6–10 minutes | 30 iterations, 3 subpopulations |

Total for all 6: 20–35 minutes on mid-range hardware.

---

## 25. Troubleshooting Guide

### Python Environment Issues

**Problem**: `ModuleNotFoundError: No module named 'e3hybrid'`
```
Forgot to install the package. Run:
pip install -e ".[dev]"
```

**Problem**: `Python was not found; run without arguments to install from the Microsoft Store`
```
Windows Store Python redirect. Use the full path to your Python executable:
.venv\Scripts\python.exe scripts/run_validation.py
```

### SUMO Issues

**Problem**: `'sumo' is not recognized as an internal or external command`
```
SUMO binary not on PATH. Either:
- Add SUMO bin directory to PATH
- Or set SUMO_HOME environment variable
```

**Problem**: `ImportError: No module named 'traci'`
```
traci is bundled with SUMO. Ensure SUMO_HOME is set:
set SUMO_HOME=C:\Program Files\SUMO
The scripts automatically add SUMO_HOME/tools to sys.path.
```

**Problem**: `traci.exceptions.TraCIException: Vehicle '...' not found`
```
The vehicle may have already arrived or teleported. This is normal during
simulation and is handled by the try/except blocks in the step loop.
```

**Problem**: `libsumo ImportError`
```
libsumo is experimental on Windows. The project falls back to TraCI automatically.
This is expected behaviour.
```

### Network Issues

**Problem**: `Error: Network file '...' not found`
```
Ensure the network file is at data/maps/midtown_manhattan.net.xml.
Run from the project root directory.
```

**Problem**: `Error: Route file '...' not found or invalid`
```
The route file may need regeneration. Run:
python scripts/run_experiment.py --algorithms dijkstra --steps 10 --vehicles 5
This will generate a route file automatically.
```

### Experiment Issues

**Problem**: `OSError: [Errno 17] File exists: 'outputs/experiments/run_...'`
```
The timestamped directory already exists (unlikely unless clock resolution is low).
Wait one second and try again, or clear the outputs/experiments/ directory.
```

**Problem**: Experiment runs but produces 0 reroutes
```
Check that the number of vehicles is high enough:
- At --vehicles 10, only a few vehicles may be active
- Increase to --vehicles 100 for meaningful rerouting
```

**Problem**: All algorithms show identical metrics
```
Check if emergency events are being injected:
- Verify --emergency-count > 0
- The graph state modification requires sufficient vehicles to route around
- Without vehicles approaching the affected edges, emergency has no visible effect
```

---

## 26. Common SUMO Errors

### "Vehicle type '...' not found"
The vehicle type referenced in the route file is not defined. All vehicles use default type "DEFAULT_VEHTYPE" which is built into SUMO.

### "Error: No connection could be made because the target machine actively refused it"
Port conflict. Another SUMO process may be running. Close all SUMO instances and try again. If using `use_libsumo=True`, switch to `use_libsumo=False` to avoid port conflicts.

### "Teleporting vehicle '...'"
SUMO teleports vehicles stuck for too long (e.g., in dead-end without reverse gear). This is expected when vehicles are routed into dead-end nodes. The `ignore-route-errors=true` setting in `sumocfg` prevents crashes.

### "Warning: Vehicle '...' has no route"
The vehicle was added but SUMO could not compute a route. This happens when:
- Source and destination are the same edge
- No path exists between source and destination (disconnected graph)
- The edge is in a different connected component

### Slow simulation with many vehicles
SUMO simulation speed depends on the number of active vehicles. 300 vehicles on a 1130-edge network runs at approximately 500-1000 steps/second on mid-range hardware. For 500+ vehicles, expect 200-500 steps/second.

---

## 27. Expected Outputs for Successful Runs

### Validation Run

```
========================================================================
  E3-HYBRID VALIDATION EXPERIMENT
========================================================================
  [1/4] E3-Hybrid source code analysis
    pheromone_matrix                            OK
    ... (all 9 OK)
  -> ALL COMPONENTS PRESENT

  [2/4] Route computation integrity (offline)
    dijkstra     PASS  det  ...
    astar        PASS  det  ...
    aco          PASS  det  ...
    bco          PASS  det  ...
    pso          PASS  det  ...
    e3hybrid     PASS  det  ...

  [3/4] Headless simulation
    [sumo] completed in 0.3s

  [4/4] Outputs
  [PASS] All 6 algorithms compute routes on the real network
  [PASS] SUMO simulation ran without errors
  Results: ...outputs/validation
```

### Full Experiment Run

```
========================================================================
  E3-HYBRID EXPERIMENT RUNNER
  Steps=300  Vehicles=300  Seed=42
  Algorithms: dijkstra, astar, aco, bco, pso, e3hybrid
========================================================================
  Output: ...outputs/experiments/run_20260709_120000

  [1/6] dijkstra
    Completed: 5.2s  ...

  ...

  [6/6] e3hybrid
    Completed: 42.1s  ...

  EXPERIMENT SUMMARY
  (Table with all 6 algorithms)
  Experiment complete.
```

### Determinism Tests

```
tests/integration/test_determinism.py::TestDeterminism::test_same_seed_identical PASSED
tests/integration/test_determinism.py::TestDeterminism::test_multi_algo_same_seed_identical PASSED
```

### All Tests

```bash
pytest -v
# Expected: 20+ tests passed (varies with environment)
```

---

## 28. GitHub Workflow (Clone to Reproduce)

This section provides a complete end-to-end workflow from cloning the repository to reproducing all thesis results.

### Step 1: Clone

```bash
git clone <repository-url> e3hybrid
cd e3hybrid
```

### Step 2: Verify Repository Integrity

```bash
# Check git status
git status
# Should show: nothing to commit, working tree clean

# Check commit hash
git rev-parse HEAD
# Record this for reproducibility
```

### Step 3: Set Up Environment

```bash
# Create virtual environment
python3.12 -m venv .venv

# Activate (Linux/macOS)
source .venv/bin/activate
# Activate (Windows)
.venv\Scripts\activate

# Install package
pip install -e ".[dev]"

# Install optional plotting dependencies
pip install matplotlib psutil
```

### Step 4: Verify SUMO Installation

```bash
# Check SUMO
sumo --version
# Must show: SUMO 1.27.1

# Check SUMO_HOME
echo $SUMO_HOME  # Linux/macOS
echo %SUMO_HOME%  # Windows
```

### Step 5: Verify Data Files

```bash
# Check network file
ls -la data/maps/midtown_manhattan.net.xml
# Should exist and be >1 MB

# Check route file
ls -la data/routes/midtown_manhattan.rou.xml
# Should exist

# Check SUMO config
ls -la data/configs/midtown_manhattan.sumocfg
# Should exist
```

### Step 6: Run Smoke Test (Validation)

```bash
python scripts/run_validation.py
# Expected: ~30 seconds, 6/6 PASS, 0 errors
```

### Step 7: Run Determinism Tests

```bash
pytest tests/integration/test_determinism.py -v
# Expected: 2 tests passed
```

### Step 8: Run Acceptance Tests

```bash
pytest tests/acceptance/ -v
# Expected: ~10 tests passed
```

### Step 9: Run Full Test Suite

```bash
pytest -v
# Expected: 20+ tests passed
```

### Step 10: Run Short Experiment

```bash
python scripts/run_experiment.py \
  --steps 50 --vehicles 20 --seed 42 --period 2.0 \
  --algorithms dijkstra,astar,aco \
  --emergency-count 1 --timeout 30
# Expected: ~5 minutes, 3 algorithms, 50 steps each
```

### Step 11: Run Full Comparative Experiment

```bash
python scripts/run_experiment.py \
  --steps 300 --vehicles 300 --seed 42 --period 1.0 \
  --algorithms dijkstra,astar,aco,bco,pso,e3hybrid \
  --reroute-interval 10 --emergency-count 3 --timeout 60
# Expected: 20-35 minutes on mid-range hardware
```

### Step 12: Verify Outputs

```bash
# Check output directory exists
ls outputs/experiments/
# Should show: run_YYYYMMDD_HHMMSS/

# Check all outputs present
ls outputs/experiments/run_*/
# Should show: metrics_summary.csv, simulation_log.csv, routing_log.csv, plots/, etc.

# Verify CSV has data
head -5 outputs/experiments/run_*/metrics_summary.csv
```

### Step 13: Reproduce Thesis Figures

See [Section 22](#22-reproducing-every-figure-used-in-the-thesis) for specific commands.

### Step 14: Archive Outputs (Optional)

```bash
# Package experiment results for archival
tar -czf thesis-experiment-results.tar.gz outputs/experiments/
```

---

*End of document. For questions, open an issue in the repository.*
