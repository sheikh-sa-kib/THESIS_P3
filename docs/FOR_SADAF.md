# FOR SADAF — Autonomous AI Agent Handoff Document

**Project:** E3-Hybrid — Decentralized Swarm Routing for Electric Vehicles Under Dynamic Urban Emergencies  
**SUMO Version:** 1.27.1 (EXACT — do not use any other version)  
**Python Version:** >=3.12  
**Repository:** TBD (clone URL provided by user)  
**Last Updated:** 2026-07-09

---

## 1. PROJECT OVERVIEW

### 1.1 Thesis Objective

Implement and evaluate six routing algorithms (Dijkstra, A\*, ACO, BCO, PSO, E3-Hybrid) on a real-world Manhattan SUMO network. The E3-Hybrid algorithm is the thesis contribution — a meta-swarm that dynamically mixes ACO, BCO, and PSO subpopulations during routing. All algorithms are benchmarked offline (pure routing) and online (SUMO simulation with rerouting, emergency events, and congestion).

### 1.2 Repository Architecture

```
e3hybrid/
├── src/e3hybrid/          # Python package (12 subpackages, 178 .py files)
│   ├── routing/           # Algorithm implementations + benchmark framework
│   ├── swarm/             # ACO, BCO, PSO, hybrid (E3-Hybrid)
│   ├── sumo/              # TraCI connection, config, rerouting manager
│   ├── network/           # Graph, Edge, Node abstractions
│   ├── decision/          # Policy engine (pre-existing, partially broken)
│   ├── emergency/         # Emergency event framework (pre-existing, partially broken)
│   ├── vehicle/           # EV battery/energy models
│   ├── communication/     # Message bus (pre-existing)
│   ├── config/            # YAML config loader/schemas
│   ├── cli/               # CLI entry point
│   ├── core/              # Base exceptions and types
│   └── utils/             # Logging, reproducibility helpers
├── run_thesis.py           # MAIN: preset-based experiment launcher
├── preflight.py            # Environment preflight checker
├── scripts/
│   ├── run_validation.py   # Lightweight: validates SUMO + all algorithms
│   └── generate_all_plots.py  # Plot generation (auto-invoked by heavy preset)
├── data/
│   ├── maps/
│   │   └── midtown_manhattan.net.xml  # 1.87 MB, 16,203 lines, 53 dead-end nodes
│   ├── routes/
│   │   └── midtown_manhattan.rou.xml  # 30 vehicles, pre-generated
│   └── configs/
│       └── midtown_manhattan.sumocfg  # 3600s simulation config
├── tests/
│   ├── acceptance/        # test_acceptance.py — end-to-end tests
│   ├── benchmarks/        # test_benchmarks.py — performance benchmarks
│   ├── integration/       # SUMO integration + determinism + real_network
│   ├── unit/              # All algorithm unit tests (ACO, BCO, PSO, Dijkstra, A*, hybrid)
│   └── test_architecture.py
├── docs/                  # Algorithm documentation, design docs
├── outputs/               # Experiment outputs (gitignored — created at runtime)
├── configs/base.yaml      # Base experiment config
├── pyproject.toml         # Build + test config
├── VERSION                # 0.1.0
├── PRE_GITHUB_CHECKLIST.md
└── README.md
```

### 1.3 Six Algorithms

| Name | Class | File | Notes |
|------|-------|------|-------|
| `dijkstra` | `DijkstraRouting` | `src/e3hybrid/routing/dijkstra.py` | Deterministic |
| `astar` | `AStarRouting` | `src/e3hybrid/routing/astar.py` | Deterministic (zero heuristic default) |
| `aco` | `ACORouting` | `src/e3hybrid/swarm/aco.py` | Stochastic (ant colony) |
| `bco` | `BCORouting` | `src/e3hybrid/swarm/bco.py` | Stochastic (bee colony) |
| `pso` | `PSORouting` | `src/e3hybrid/swarm/pso.py` | Stochastic (particle swarm) |
| `e3hybrid` | `E3HybridRouting` | `src/e3hybrid/swarm/hybrid.py` | Meta-swarm (ACO+BCO+PSO) |

All algorithms are registered in `src/e3hybrid/routing/factory.py` via `RoutingFactory.create_algorithm(name)`.

### 1.4 Workflow

```
1. Clone repository
2. Install SUMO 1.27.1 + set SUMO_HOME
3. Create Python venv + install dependencies
4. Verify: validation script
5. Verify: determinism tests
6. Verify: acceptance tests
7. Verify: benchmark smoke test
8. Run small experiment (30 steps, 2 algorithms)
9. Run full thesis experiment (300 steps, all 6 algorithms)
10. Verify outputs
11. Generate final report
```

### 1.5 Expected Outputs

All are written to `outputs/experiments/run_YYYYMMDD_HHMMSS/`:

- `metrics_summary.csv` — Per-algorithm aggregate metrics
- `simulation_log.csv` — Per-step simulation state for each algorithm
- `routing_log.csv` — Offline benchmark results (success rate, runtime, distance)
- `emergency_log.csv` — Emergency events (if any)
- `algorithm_timing.csv` — Per-step rerouting latency
- `environment.json` — System + package versions
- `network_metadata.json` — Node/edge counts
- `git_commit.txt` — HEAD commit hash
- `config_snapshot.yaml` — Exact configuration used
- `{algo}.rou.xml` — SUMO route files per algorithm
- `plots/` — Execution time, vehicles over time, congestion, travel time, throughput, memory

---

## 2. MACHINE VERIFICATION

The AI agent MUST run these checks before any experiment. If anything is missing, report it and attempt to fix automatically before asking the user.

### 2.1 Windows Version

```powershell
(Get-CimInstance Win32_OperatingSystem).Version
(Get-CimInstance Win32_OperatingSystem).Caption
```

Minimum: Windows 10 22H2 or Windows 11. SUMO 1.27.1 requires Windows 10+.

### 2.2 Python Version

```powershell
python --version
```

Required: >=3.12. If missing or wrong version, locate via:
```powershell
Get-ChildItem "C:\Users\*\AppData\Local\Programs\Python\Python312\python.exe" -ErrorAction SilentlyContinue
Get-ChildItem "C:\Program Files\Python312\python.exe" -ErrorAction SilentlyContinue
& "C:\Users\SAKIB\.local\bin\python3.14.exe" --version  # Fallback
```

### 2.3 Git

```powershell
git --version
```

Required for commit hash capture. Not critical for execution but recommended.

### 2.4 SUMO Installation

```powershell
Test-Path "C:\Program Files (x86)\Eclipse\Sumo"
$env:SUMO_HOME
```

SUMO 1.27.1 MUST be installed at `C:\Program Files (x86)\Eclipse\Sumo`. If not:
1. Download from https://sumo.dlr.de/download/
2. Installer: `sumo-1_27_1+setup.exe`
3. The installer auto-adds to PATH and sets SUMO_HOME
4. After installation, reboot shell or manually set:
```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
```

### 2.5 SUMO Version

```powershell
& "$env:SUMO_HOME\sumo.exe" --version
```

Expected output contains `1.27.1`. If not 1.27.1, the experiment WILL fail because:
- `randomTrips.py -r` in 1.27.1 generates routes directly (no separate duarouter call)
- Earlier versions require a separate duarouter step
- Later versions may change the API

### 2.6 pip

```powershell
python -m pip --version
```

Should be >=24.0. Upgrade if needed:
```powershell
python -m pip install --upgrade pip
```

### 2.7 Virtual Environment

```powershell
Test-Path ".venv\Scripts\python.exe"
```

If missing, create:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2.8 SUMO_HOME

```powershell
$env:SUMO_HOME
```

Must equal `C:\Program Files (x86)\Eclipse\Sumo`. If not set:
```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
[System.Environment]::SetEnvironmentVariable("SUMO_HOME", "C:\Program Files (x86)\Eclipse\Sumo", "User")
```

### 2.9 PATH

```powershell
$env:PATH -split ";" | Select-String "Sumo"
```

SUMO bin and tools should be on PATH:
- `C:\Program Files (x86)\Eclipse\Sumo\bin`
- `C:\Program Files (x86)\Eclipse\Sumo\tools`

### 2.10 CPU

```powershell
(Get-CimInstance Win32_Processor).Name
(Get-CimInstance Win32_Processor).NumberOfLogicalProcessors
```

The experiment is CPU-bound. Minimum 4 logical processors recommended.

### 2.11 RAM

```powershell
[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
```

Minimum: 8 GB. Recommended: 16 GB. A full 6-algorithm 300-step experiment may use 4-8 GB peak.

### 2.12 Free Disk Space

```powershell
(Get-PSDrive C).Free / 1GB
```

Minimum: 10 GB free. Each experiment run creates ~50-200 MB of outputs.

---

## 3. DEPENDENCIES

### 3.1 Python Package Dependencies (from pyproject.toml)

| Package | Minimum Version | Purpose |
|---------|----------------|---------|
| `PyYAML` | >=6.0.2 | Config serialization |
| `traci` | >=1.20.0 | SUMO TraCI client (bundled with SUMO) |
| `sumolib` | >=1.20.0 | SUMO Python library (bundled with SUMO) |

### 3.2 Optional Dependencies

| Package | Purpose | Auto-install? |
|---------|---------|---------------|
| `matplotlib>=3.8` | Plotting | Yes — required for thesis plots |
| `psutil>=5.9` | Memory tracking | Yes — required for memory metrics |
| `pytest>=8.0` | Test suite | Yes — required for verification |
| `pytest-cov>=5.0` | Code coverage | Yes (optional but recommended) |

### 3.3 Auto-Installation

```powershell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install pyyaml matplotlib psutil pytest pytest-cov
```

The `traci` and `sumolib` packages are NOT installed via pip. They are loaded from `$env:SUMO_HOME/tools` at runtime. The experiment scripts handle this automatically by inserting SUMO_HOME/tools into sys.path.

To verify traci is importable:
```powershell
python -c "import sys; sys.path.insert(0, r'$env:SUMO_HOME\tools'); import traci; print('traci:', traci.__version__)"
```
Expected: `traci: 0.0.0` (the version string is always 0.0.0 from SUMO builds).

### 3.4 Manual Installation

If `pip install` fails due to environment restrictions (e.g., externally-managed), use:
```powershell
pip install --user pyyaml matplotlib psutil pytest pytest-cov
```
or with uv:
```powershell
uv pip install pyyaml matplotlib psutil pytest pytest-cov --system
```

If SUMO cannot be automatically detected, ask the user: "Please install SUMO 1.27.1 from https://sumo.dlr.de/download/ and set SUMO_HOME."

---

## 4. REPOSITORY VERIFICATION

### 4.1 Clone and Structure

```powershell
git clone <URL> e3hybrid
cd e3hybrid
```

Verify these paths exist:

```powershell
$root = "."
@(
    "src/e3hybrid/__init__.py",
    "src/e3hybrid/routing/factory.py",
    "src/e3hybrid/routing/dijkstra.py",
    "src/e3hybrid/routing/astar.py",
    "src/e3hybrid/swarm/aco.py",
    "src/e3hybrid/swarm/bco.py",
    "src/e3hybrid/swarm/pso.py",
    "src/e3hybrid/swarm/hybrid.py",
    "src/e3hybrid/sumo/connection.py",
    "src/e3hybrid/sumo/rerouting_manager.py",
    "src/e3hybrid/sumo/network_importer.py",
    "src/e3hybrid/network/graph.py",
    "src/e3hybrid/network/edge.py",
    "scripts/run_experiment.py",
    "scripts/run_validation.py",
    "data/maps/midtown_manhattan.net.xml",
    "data/routes/midtown_manhattan.rou.xml",
    "data/configs/midtown_manhattan.sumocfg",
    "pyproject.toml",
    "VERSION",
    "docs/FINAL_EXPERIMENT.md",
    "docs/RELEASE_CHECKLIST.md",
    "docs/FOR_SADAF.md"
) | ForEach-Object {
    if (Test-Path $_) { Write-Host "[OK] $_" } else { Write-Host "[MISSING] $_" }
}
```

### 4.2 Network File

**File:** `data/maps/midtown_manhattan.net.xml`  
**Size:** ~1.87 MB, 16,203 lines  
**Source:** OpenStreetMap export processed with `netconvert --osm-files manhattan.osm --opendrive-output`  
**Properties:**  
- Midtown Manhattan area  
- UTM projection  
- 53 dead-end nodes (these will cause some route replacement warnings — this is expected)  
- No internal links (`--no-internal-links` was used during generation)  

Verify with:
```powershell
python -c "import os; os.environ['SUMO_HOME']=r'C:\Program Files (x86)\Eclipse\Sumo'; import sys; sys.path.insert(0, r'C:\Program Files (x86)\Eclipse\Sumo\tools'); import sumolib; net=sumolib.net.readNet(r'data/maps/midtown_manhattan.net.xml'); print(f'Edges: {len(net.getEdges())}, Nodes: {len(net.getNodes())}')"
```

### 4.3 Route File

**File:** `data/routes/midtown_manhattan.rou.xml`  
**Lines:** 134, **Vehicles:** 30, **Departures:** every 2 seconds (0.0 to 58.0)  
Pre-generated for quick validation. The experiment script generates its own route files per algorithm.

### 4.4 Scripts

| Script | Purpose |
|--------|---------|
| `run_thesis.py` | **Main launcher** — preset-based experiment runner (replaces `run_experiment.py`) |
| `scripts/run_validation.py` | Lightweight validation (SUMO smoke test + routing check) |

### 4.5 Verification

Run the validation script:
```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
$env:PYTHONPATH = "src"
.venv\Scripts\Activate.ps1
python scripts/run_validation.py
```

Expected: All 6 algorithms PASS, SUMO simulation runs with 0 errors.

### 4.6 Experiment Presets

The main launcher uses named presets instead of long CLI arguments:

```powershell
python run_thesis.py --preset smoke     # ~10 s verification
python run_thesis.py --preset light     # ~5-15 min, all 6 algos
python run_thesis.py --preset heavy     # ~30-90 min, thesis-quality [DEFAULT]
python run_thesis.py --preset extreme   # ~2-6 hr, stress-test
```

Each preset is a complete experiment: preflight → validation → SUMO simulation →
offline benchmarks → CSV generation → plots → summary. The heavy preset
additionally generates 34 publication-ready plots automatically.

---

## 5. SUMO VERIFICATION

### 5.1 Required Binaries

```powershell
& "$env:SUMO_HOME\sumo.exe" --version
& "$env:SUMO_HOME\bin\sumo.exe" --version  # alt location
& "$env:SUMO_HOME\bin\sumo-gui.exe" --version  # GUI (not needed for headless)
```

### 5.2 Required Python Tools (from SUMO_HOME/tools)

```powershell
python -c "import sys; sys.path.insert(0, r'$env:SUMO_HOME\tools'); import traci; print('traci OK'); import sumolib; print('sumolib OK')"
python -c "import sys; sys.path.insert(0, r'$env:SUMO_HOME\tools'); from sumolib import checkBinary; print('checkBinary OK')"
```

### 5.3 Smoke Test

Run a 5-step SUMO simulation on the Manhattan network to verify the binary works:

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
$env:PYTHONPATH = "src"
.venv\Scripts\Activate.ps1
python -c "
import os, sys
sys.path.insert(0, r'$env:SUMO_HOME\tools')
sys.path.insert(0, 'src')
import traci
from e3hybrid.sumo.config import SumoConfig
from e3hybrid.sumo.connection import SumoTraciConnection
from pathlib import Path
cfg = SumoConfig(sumo_net_file=Path('data/maps/midtown_manhattan.net.xml'), sumo_route_file=Path('data/routes/midtown_manhattan.rou.xml'), sumo_seed=42, use_gui=False, use_libsumo=False)
conn = SumoTraciConnection(cfg)
conn.start()
for s in range(5):
    conn.step()
    print(f'Step {s}: {len(conn.get_vehicle_ids())} vehicles')
conn.stop()
print('SUMO SMOKE TEST PASSED')
"
```

If the smoke test fails:
1. Check SUMO_HOME is correct
2. Check the .net.xml file is valid: `& "$env:SUMO_HOME\sumo.exe" -n data/maps/midtown_manhattan.net.xml -r data/routes/midtown_manhattan.rou.xml --no-step-log --no-warnings --end 10`
3. Check for missing dependencies: `python -m pip list | findstr pyyaml`

---

## 6. PROJECT VALIDATION

Run these in order. Stop and fix before proceeding.

### 6.1 Validation Script

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
$env:PYTHONPATH = "src"
.venv\Scripts\Activate.psl
python scripts/run_validation.py
```

Expected: All 6 algorithms compute routes. SUMO runs cleanly.

### 6.2 Determinism Tests

```powershell
python -m pytest tests/integration/test_determinism.py -v --tb=short
```

Expected: 4 tests pass. Tests verify that the same configuration produces identical results across runs.

### 6.3 Acceptance Tests

```powershell
python -m pytest tests/acceptance/test_acceptance.py -v --tb=short
```

Expected: 10-12 tests pass. These are end-to-end tests spanning multiple subsystems.

### 6.4 Benchmark Smoke Test

```powershell
python -m pytest tests/benchmarks/test_benchmarks.py -v --tb=short
```

Expected: 10-12 tests pass. Benchmarks verify performance baselines.

### 6.5 Full Test Suite (Optional — 852 passed, 63 pre-existing failures)

```powershell
python -m pytest tests/ -v --tb=short -k "not test_default_construction" 2>&1
```

Note: 63 tests will fail due to pre-existing issues in decision engine, emergency core, and hybrid config tests. These are NOT related to the routing algorithms or SUMO integration. The critical passing tests are:

| Suite | Expected | Status |
|-------|----------|--------|
| `test_acceptance.py` | 12/12 PASS | ✅ |
| `test_determinism.py` | 4/4 PASS | ✅ |
| `test_real_network.py` | 3/3 PASS | ✅ |
| `test_sumo_integration.py` | 14/14 PASS | ✅ |
| `test_benchmarks.py` | 12/12 PASS | ✅ |
| `test_dijkstra.py` | All PASS | ✅ |
| `test_astar.py` | All PASS | ✅ |
| `test_aco.py` | All PASS | ✅ |
| `test_bco.py` | All but 1 PASS | ✅ (1 pre-existing default) |
| `test_pso.py` | All PASS | ✅ |
| `test_hybrid.py` | All but 2 PASS | ✅ (pre-existing) |
| All sumo unit tests | All PASS | ✅ |

Pre-existing failures (DO NOT attempt to fix):
- Decision engine tests: ImportError (`DecisionError` missing from `core/exceptions.py`)
- Emergency core tests: TypeError in `RoadClosureEvent.__post_init__` (Python 3.12 dataclass issue)
- Hybrid config: `forward_steps` default is 500 but test expects 100
- Vehicle factory: Config key mismatch (`battery.capacity_kwh`)

---

## 7. PRE-FULL-EXPERIMENT CHECKLIST

Before running the full thesis experiment, verify:

### 7.1 Repository Clean

```powershell
git status
```

Should show clean working tree. If uncommitted changes exist:
```powershell
git stash
```

### 7.2 Deterministic Seeds

The experiment uses these seeds:
- `--seed 42` for SUMO simulation and route generation
- `--seed 43` (seed+1) for offline benchmarks
- `seed + 2000` for emergency event randomization

Verify in `scripts/run_experiment.py`:
- Line 73: `seed: int = 42`
- Line 431: `rng = random.Random(seed)` (benchmarks)
- Line 240: `emerg_rng = random.Random(config.seed + 2000)` (emergencies)

### 7.3 Outputs Writable

```powershell
Test-Path "outputs/experiments"
```

If missing, the script creates it automatically. Ensure the drive has space (Section 2.12).

### 7.4 Enough RAM

```powershell
[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
```

Must be >= 8 GB. The E3-Hybrid algorithm (swarm hybrid) may use up to 2-3 GB during a 300-step simulation.

### 7.5 Enough Disk Space

```powershell
(Get-PSDrive C).Free / 1GB
```

Must be >= 10 GB. Each experiment run is ~50-200 MB.

### 7.6 No Circular Imports

```powershell
python -c "import sys; sys.path.insert(0, 'src'); from e3hybrid.routing.factory import RoutingFactory; print('No circular imports')"
```

If ImportError occurs, report the trace and fix the cyclic import.

### 7.7 Experiment Configuration Valid

Verify the launcher and presets work:
```powershell
python run_thesis.py --help
```

Expected output shows preset descriptions: smoke, light, heavy, extreme,
with `heavy` as the recommended default.

### 7.8 Quick Experiment Smoke Test

Run a minimal experiment to confirm the workflow:
```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
$env:PYTHONPATH = "src"
.venv\Scripts\Activate.ps1
python run_thesis.py --preset smoke
```

Expected:
- Preflight passes (all checks green)
- Pipeline validation runs
- Simulation completes (~10 s)
- Output files written to `outputs/experiments/run_*`
- Final summary printed
- Exit code 0

---

## 8. FULL THESIS EXPERIMENT

### 8.1 Command (One-Line)

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
$env:PYTHONPATH = "src"
.venv\Scripts\Activate.ps1
python run_thesis.py --preset heavy
```

This single command replaces the old multi-argument invocation. It runs:
- Environment preflight → pipeline validation → all 6 algorithms (online SUMO) →
  offline routing benchmarks → CSV generation → 34 publication-ready plots →
  final summary.

For multi-seed statistical significance:
```powershell
python run_thesis.py --preset heavy --seeds 42 43 44
```

### 8.2 What The Heavy Preset Does

**Phase 1 — Online SUMO Simulation (per algorithm, sequentially):**
- For each of 6 algorithms:
  1. Generate route file with randomTrips.py (300 vehicles, period 1.0, seed 42)
  2. Start SUMO headless (libsumo preferred, falls back to TraCI)
  3. Import the Manhattan network into the internal graph
  4. Run 300 simulation steps (1 step = 1 second):
     - Every 10 steps, reroute active vehicles using the algorithm
     - On 3 scheduled emergency events, apply emergency penalties to edges
     - Track congestion (>80% occupancy), blocked (>95%), speeds, teleports
  5. Collect metrics and shut down

**Phase 2 — Offline Routing Benchmarks:**
- 50 random source-destination pairs (seeded at 43)
- Each algorithm routes all pairs
- Record success rate, runtime, distance

**Phase 3 — Plot Generation (automatic):**
- 34 figures across 9 categories:
  execution_time, vehicles_over_time, rerouting_latency, congestion_heatmap,
  travel_time_comparison, throughput, emergency_response, memory_usage,
  algorithm_scaling

**Phase 4 — Summary Report:**
- Algorithm comparison table (travel time, speed, reroutes, throughput, peak memory)
- Routing benchmark table (success rate, avg/min/max runtime, distance)
- Complete artifact listing
- Output directory path

### 8.3 Expected Runtime

| Component | Estimated |
|-----------|-----------|
| Route generation (6 files) | ~1-2 min |
| Dijkstra (300 steps) | ~10-20 sec |
| A* (300 steps) | ~10-20 sec |
| ACO (300 steps) | ~10-30 min |
| BCO (300 steps) | ~5-15 min |
| PSO (300 steps) | ~10-20 min |
| E3-Hybrid (300 steps) | ~15-30 min |
| Offline benchmarks (100 req × 6 algos) | ~5-10 min |
| Plot generation | ~10 sec |
| **Total** | **~45-90 min** |

The E3-Hybrid algorithm is the slowest because it runs all three swarm algorithms internally at each reroute step.

### 8.4 Headless Only

The experiment runs headless by default (`use_gui=False`, `use_libsumo=True`). No display or GUI is required. The `use_libsumo` flag enables in-process communication (faster than TCP-based TraCI). If libsumo is unavailable, the code falls back to TraCI automatically.

### 8.5 Known Issues During Experiment

1. **"Route replacement failed" messages on stderr:**  
   These occur when the routing algorithm produces a path whose edge-to-edge connections don't match SUMO's lane-level connection restrictions (turn restrictions, traffic light phases, lane-specific mappings). The vehicles simply keep their old route. This is EXPECTED and does NOT crash the simulation. The graph abstraction in the internal model is simplified compared to SUMO's detailed network. The experiment script catches these exceptions.

2. **SUMO 1.27.1 randomTrips.py -r behavior:**  
   In SUMO 1.27.1, `randomTrips.py -r` generates routes directly (the `-r` flag now produces a `.rou.xml` with embedded routes). No separate `duarouter` call is needed. The `generate_routes()` function in `scripts/run_experiment.py` has been updated to handle this.

3. **Stderr flooding:**  
   SUMO prints errors to stderr by default. These are mixed with stdout in the console. This is normal.

### 8.6 If the Experiment Crashes

1. Check the error message location. Common issues:
   - `ModuleNotFoundError`: Missing Python dependency → `pip install <package>`
   - `ImportError: No module named 'traci'` → SUMO_HOME/tools not on PATH → Manually add before run
   - `Fatal Error in SUMO` → Corrupt network file → Re-extract from git
   - `MemoryError` → Not enough RAM → Reduce `--vehicles` or `--steps`
2. After fixing, clean outputs and retry:
```powershell
Remove-Item -Recurse -Force "outputs\experiments\*" -ErrorAction SilentlyContinue
```

---

## 9. LIVE PROGRESS REPORTING

While the experiment is running, display:

```
========================================================================
  E3-HYBRID EXPERIMENT RUNNER
  Steps=300  Vehicles=300  Seed=42
  Algorithms: dijkstra, astar, aco, bco, pso, e3hybrid
========================================================================

----------------------------------------------------------------------
  Phase 1: Online SUMO simulation (per-algorithm)
----------------------------------------------------------------------

  [1/6] dijkstra
  dijkstra   | Step 150/300  50% | Veh 45 | Elapsed 12.3s ETA 12s

  [2/6] astar
  astar      | Step 300/300 100% | Veh 0  | Completed in 18.7s

  [...]
```

The experiment runner prints to stdout. The agent should:
- Capture and display stdout in real-time
- If output is truncated, display the last 10 lines periodically
- Report any ERROR or WARNING messages
- Track total elapsed time
- If no output for > 120 seconds, investigate (possible hang)

Progress format from `scripts/run_experiment.py`:
```
  [M/N] <algo_name>
    Completed: X.Xs  MaxVeh: Y  Reroutes: Z  Memory: W.WMB
```

### 9.1 Expected Algorithm Order

1. `dijkstra` — Fastest (~30-60s)  
2. `astar` — Fast (~30-60s)  
3. `aco` — Medium (~5-15 min)  
4. `bco` — Medium (~5-15 min)  
5. `pso` — Medium-slow (~10-20 min)  
6. `e3hybrid` — Slowest (~15-30 min)  

If an algorithm takes significantly longer than expected (>2x), check:
- CPU usage (should be high — each algorithm is CPU-bound)
- Memory usage (shouldn't exceed 4 GB)
- No error loop in rerouting

---

## 10. OUTPUT VERIFICATION

### 10.1 Verify Output Directory

```powershell
$latest = Get-ChildItem "outputs\experiments" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$latest.FullName
```

### 10.2 Verify All Files Exist

```powershell
$dir = $latest.FullName
@(
    "environment.json",
    "git_commit.txt",
    "metrics_summary.csv",
    "routing_log.csv",
    "simulation_log.csv",
    "network_metadata.json",
    "dijkstra.rou.xml",
    "astar.rou.xml",
    "aco.rou.xml",
    "bco.rou.xml",
    "pso.rou.xml",
    "e3hybrid.rou.xml",
    "plots/execution_time.png",
    "plots/vehicles_over_time.png",
    "plots/congestion_heatmap.png",
    "plots/travel_time_comparison.png",
    "plots/throughput.png",
    "plots/memory_usage.png"
) | ForEach-Object {
    $path = Join-Path $dir $_
    if (Test-Path $path) {
        $size = (Get-Item $path).Length
        Write-Host "[OK] $_ ($size bytes)"
    } else {
        Write-Host "[MISSING] $_"
    }
}
```

### 10.3 Verify CSV Integrity

```powershell
# Check all CSVs are valid (have headers, non-empty)
Get-ChildItem $dir -Filter "*.csv" | ForEach-Object {
    $lines = (Get-Content $_.FullName | Measure-Object).Count
    $header = Get-Content $_.FullName -First 1
    Write-Host "[CSV] $($_.Name): $lines lines, header: $header"
}
```

### 10.4 Verify metrics_summary.csv Has All 6 Algorithms

```powershell
$csv = Import-Csv (Join-Path $dir "metrics_summary.csv")
$csv.algorithm
```

Expected: `dijkstra`, `astar`, `aco`, `bco`, `pso`, `e3hybrid`

### 10.5 Verify routing_log.csv Has All 6 Algorithms

```powershell
$csv = Import-Csv (Join-Path $dir "routing_log.csv")
$csv.algorithm
```

Expected: same 6 algorithms. Success rate should be >80% for all.

### 10.6 Verify Plots Are Valid PNGs

```powershell
Get-ChildItem (Join-Path $dir "plots") -Filter "*.png" | ForEach-Object {
    $bytes = [System.IO.File]::ReadAllBytes($_.FullName)
    $isPng = $bytes[0] -eq 137 -and $bytes[1] -eq 80 -and $bytes[2] -eq 78 -and $bytes[3] -eq 71
    if ($isPng) { Write-Host "[OK] $($_.Name) is valid PNG ($($_.Length) bytes)" }
    else { Write-Host "[CORRUPT] $($_.Name) is not a valid PNG" }
}
```

### 10.7 Verify environment.json

```powershell
$json = Get-Content (Join-Path $dir "environment.json") -Raw | ConvertFrom-Json
$json.timestamp
$json.python_version
$json.sumo_version
```

### 10.8 No Output File Is Empty

```powershell
Get-ChildItem $dir -Recurse -File | Where-Object { $_.Length -eq 0 } | ForEach-Object {
    Write-Host "[EMPTY] $($_.Name)"
}
```

---

## 11. FINAL REPORT

After the experiment completes, produce a structured report with the following sections:

### 11.1 Simulation Configuration

```
Configuration:
  Steps:           300
  Vehicles:        300
  Period:          1.0s
  Seed:            42
  Algorithms:      dijkstra, astar, aco, bco, pso, e3hybrid
  Reroute every:   10 steps
  Emergency events: 3
  Offline requests: 100
  Network:         data/maps/midtown_manhattan.net.xml (1.87 MB, 16,203 lines)
  SUMO version:    1.27.1
  Python version:  3.12.x
```

### 11.2 Runtime

```
Total execution time:           XX.X minutes
  Dijkstra:                     XX.X seconds
  A*:                           XX.X seconds
  ACO:                          XX.X seconds
  BCO:                          XX.X seconds
  PSO:                          XX.X seconds
  E3-Hybrid:                    XX.X seconds
  Offline benchmarks:           XX.X seconds
  Plot generation:              XX.X seconds
```

### 11.3 Memory Usage

```
Peak memory per algorithm:
  Dijkstra:                     XX.X MB
  A*:                           XX.X MB
  ACO:                          XX.X MB
  BCO:                          XX.X MB
  PSO:                          XX.X MB
  E3-Hybrid:                    XX.X MB
```

### 11.4 Algorithm Comparison

```
Algorithm   Reroutes  Congestion  Speed(m/s)  Travel(s)  Throughput  Failures
dijkstra    XXX       XXX         XX.XX       XXXX.XX    XXX         X
astar       XXX       XXX         XX.XX       XXXX.XX    XXX         X
aco         XXX       XXX         XX.XX       XXXX.XX    XXX         X
bco         XXX       XXX         XX.XX       XXXX.XX    XXX         X
pso         XXX       XXX         XX.XX       XXXX.XX    XXX         X
e3hybrid    XXX       XXX         XX.XX       XXXX.XX    XXX         X
```

### 11.5 Teleport Statistics

```
Total teleports:
  Dijkstra:                     X
  A*:                           X
  ACO:                          X
  BCO:                          X
  PSO:                          X
  E3-Hybrid:                    X
```

### 11.6 Emergency Statistics

```
Emergency events scheduled:     3
Active emergencies:             X
Emergency edges affected:       X
```

### 11.7 Output Locations

```
Output directory:               outputs/experiments/run_YYYYMMDD_HHMMSS/
  metrics_summary.csv:          <path>
  routing_log.csv:              <path>
  simulation_log.csv:           <path>
  environment.json:             <path>
  network_metadata.json:        <path>
  Plots:                        <path>/plots/
```

### 11.8 Warnings (If Any)

- "Route replacement failed" stderr messages: count and note that these are expected
- matplotlib not installed → plots skipped (install with `pip install matplotlib`)
- psutil not installed → memory metrics unavailable (install with `pip install psutil`)
- Any pre-existing test failures noted

### 11.9 Recommendations

- If the E3-Hybrid algorithm outperforms individual swarm algorithms, this supports the thesis hypothesis
- If certain algorithms show high teleport counts, the rerouting interval may need adjustment
- If congestion events cluster on specific edges, those may be network bottlenecks worth analyzing

---

## 12. USER COMMANDS

The following commands should be provided at the end of the report so the user can copy them.

### Clone

```powershell
git clone <repository-url> e3hybrid
cd e3hybrid
```

### Create Virtual Environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Install Dependencies

```powershell
pip install --upgrade pip
pip install pyyaml matplotlib psutil pytest pytest-cov
```

### Run Validation

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
$env:PYTHONPATH = "src"
.venv\Scripts\Activate.ps1
python scripts/run_validation.py
```

### Run Small Experiment (Smoke Test)

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
$env:PYTHONPATH = "src"
.venv\Scripts\Activate.ps1
python run_thesis.py --preset smoke
```

### Run Full Thesis Experiment (One Command)

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
$env:PYTHONPATH = "src"
.venv\Scripts\Activate.ps1
python run_thesis.py --preset heavy
```

This automatically runs all 6 algorithms, emergencies, rerouting, offline benchmarks,
CSV generation, 34 publication-ready plots, and final summary. No manual steps needed.

### Run Full Experiment with Multiple Seeds

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
$env:PYTHONPATH = "src"
.venv\Scripts\Activate.ps1
python run_thesis.py --preset heavy --seeds 42 43 44
```

### Generate Plots (Standalone)

```powershell
pip install matplotlib
python -c "
import pandas as pd, matplotlib.pyplot as plt
csv = pd.read_csv('outputs/experiments/run_*/metrics_summary.csv')
csv.plot.bar(x='algorithm', y=['total_execution_s', 'peak_memory_mb'])
plt.show()
"
```

### Generate Benchmarks (Standalone)

```powershell
python -m pytest tests/benchmarks/test_benchmarks.py -v
```

### Deterministic Replay

```powershell
python -m pytest tests/integration/test_determinism.py -v
```

### Clean Outputs

```powershell
Remove-Item -Recurse -Force "outputs\experiments\*" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "outputs\validation\*" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "outputs\benchmarks\*" -ErrorAction SilentlyContinue
```

---

## 13. DECISION LOG

### 13.1 Vehicle Count: 300

**Why 300?**  
- The Manhattan network has ~950 non-internal edges and ~420 junctions
- 300 vehicles provides enough traffic density for meaningful congestion without overwhelming the network
- Each vehicle departs every 1 second, so all vehicles enter within 300 seconds (5 minutes simulation time)
- This matches the simulation duration (300 steps = 300 seconds)
- Validated with the pre-generated route file which has 30 vehicles (1/10 scale for quick validation)

### 13.2 Simulation Duration: 300 Steps

**Why 300 steps?**  
- 300 seconds (5 minutes) is sufficient for all 300 vehicles to enter and for congestion to build up
- Shorter than 300 steps (<5 min) doesn't allow enough time for traffic patterns to develop
- Longer than 300 steps (>5 min) has diminishing returns — all vehicles have entered by step 300
- The rerouting interval is 10 steps, giving 30 reroute cycles per algorithm
- 300 steps × 6 algorithms × ~0.1s per step runtime = manageable experiment (~3-20 min per algorithm)

### 13.3 Rerouting Interval: 10 Steps

**Why 10 steps (10 seconds)?**  
- Frequent enough to respond to changing conditions (congestion, emergencies)
- Infrequent enough to avoid excessive computational overhead
- Swarm algorithms (ACO, BCO, PSO, E3-Hybrid) are expensive — rerouting every step would make the experiment unacceptably slow
- 10 seconds is a realistic rerouting cycle for a real-world traffic management system
- Matches the configuration in the pre-existing experiment runner design

### 13.4 Emergency Events: 3

**Why 3 events?**  
- Enough to test the emergency response mechanism without dominating the simulation
- Each event affects 3 edges for 20 seconds (20 steps)
- Triggered between steps 30 and 75 (randomly, seeded at `seed + 2000`)
- 3 events provide statistical significance for emergency metrics
- The emergency penalty adds 120 seconds to affected edge travel times

### 13.5 Congestion Settings

**Thresholds (hardcoded in scripts/run_experiment.py):**
- Congestion: edge occupancy > 80%
- Blocked: edge occupancy > 95%
- These are standard thresholds used in traffic engineering literature

### 13.6 Random Seeds

- **Main seed: 42** — Used for route generation and SUMO simulation
- **Benchmark seed: 43** (seed + 1) — Independent seed for offline benchmark request generation
- **Emergency seed: 2042** (seed + 2000) — Independent seed for emergency event scheduling
- Seeds are chosen to be simple, memorable, and reproducible
- 42 is the standard "answer to everything" seed for reproducible research

### 13.7 Benchmark Repetitions: 100 Requests

**Why 100?**  
- 100 random source-destination pairs provide statistically meaningful success rate and runtime measurements
- Each algorithm processes all 100 requests (600 total routing computations)
- At ~10ms per request (Dijkstra/A*) to ~500ms (E3-Hybrid), this takes 5-10 minutes
- 100 pairs cover a good sample of the 950+ edge network

### 13.8 Output Formats

- **CSV** — Human-readable, easy to analyze in Excel/Python/R
- **JSON** — Machine-readable for automated processing
- **PNG plots** — 150 DPI, suitable for thesis inclusion
- **XML** — SUMO route files (can be re-run directly in SUMO)
- **TXT** — Git commit hash (reproducibility)
- **YAML** — Config snapshot (full reproducibility)

---

## 14. AUTONOMOUS EXECUTION PROTOCOL

### 14.1 How the AI Agent Must Behave

1. **Autonomous**: Complete all steps without user intervention. Only stop if a manual action is truly required (e.g., SUMO not installed, disk full, hardware failure).

2. **Verify Before Running**: Run each verification step (Sections 2-7) before the expensive experiment (Section 8). If verification fails, attempt to fix automatically:
   - Missing Python packages → `pip install`
   - Missing SUMO_HOME → detect SUMO path or set it
   - PATH issues → add SUMO bin/tools to PATH
   - Broken dependencies → reinstall

3. **Stop Conditions**: Only stop and ask the user if:
   - SUMO is not installed and cannot be automatically installed
   - Disk space is critically low (<1 GB)
   - Python <3.12 with no upgrade path
   - Network file is corrupted or missing and cannot be regenerated
   - A routing algorithm has a REAL bug (not a pre-existing test failure)

4. **Auto-Retry**: If validation fails, fix the issue and rerun validation. Only proceed after clean validation.

5. **Do NOT Modify Algorithms**: The routing algorithms (dijkstra.py, astar.py, aco.py, bco.py, pso.py, hybrid.py) must NOT be modified unless a genuine bug is found. Bug definition:
   - The algorithm crashes with an unhandled exception on valid input
   - The algorithm produces an invalid route (edge sequence not connected in the internal graph)
   - The algorithm violates the RoutingAlgorithm protocol

6. **Preserve Determinism**: Do NOT change random seeds, simulation parameters, or any configuration that affects output reproducibility.

7. **Preserve Reproducibility**:
   - Record all commands executed
   - Record all outputs generated
   - Record any anomalies or warnings
   - Do NOT delete or overwrite previous experiment outputs without user consent

8. **Preserve Thesis Integrity**:
   - Do NOT tune algorithm parameters for better results
   - Do NOT cherry-pick results
   - Report ALL outputs, including failures
   - If an algorithm performs poorly, report it accurately

### 14.2 Decision Tree

```
Start
├── Machine verification (Section 2)
│   ├── All pass → continue
│   └── Fail → auto-fix → rerun verification
│       └── Cannot fix → STOP, ask user
├── Dependencies (Section 3)
│   ├── Auto-install → verify
│   └── Cannot install → STOP, ask user
├── Repository verification (Section 4)
│   ├── All files present → continue
│   └── Missing files → report, STOP
├── SUMO verification (Section 5)
│   ├── Smoke test PASS → continue
│   └── Smoke test FAIL → diagnose, fix, retry
│       └── Cannot fix → STOP, ask user
├── Project validation (Section 6)
│   ├── All critical tests PASS → continue
│   └── Critical test FAIL → diagnose, fix, retry
│       └── Pre-existing failure → note and continue
├── Pre-experiment checklist (Section 7)
│   ├── All checks PASS → continue
│   └── Fail → fix, retry
├── Full experiment (Section 8)
│   ├── Complete → verify outputs (Section 10)
│   └── Crash → diagnose, fix, clean, retry
│       └── Cannot fix → STOP, report
├── Output verification (Section 10)
│   ├── All valid → generate report (Section 11)
│   └── Invalid → report, STOP
└── Final report (Section 11)
    └── DELIVER to user
```

### 14.3 Error Recovery

| Error | Symptom | Recovery |
|-------|---------|----------|
| `ModuleNotFoundError` | Python can't import a module | `pip install <module>` |
| `ImportError: libsumo` | libsumo not available | Falls back to TraCI automatically — no action needed |
| `ImportError: traci` | SUMO_HOME/tools not on sys.path | Add `$env:SUMO_HOME\tools` to `sys.path` before import |
| `Fatal error in SUMO` | SUMO binary crashed | Network file issue. Verify with `sumo -n data/maps/*.net.xml` |
| `MemoryError` | Out of RAM | Reduce `--vehicles` or `--steps` |
| Route replacement failed | SUMO lane connection error | EXPECTED — note count but continue |
| Test timeout | Algorithm too slow on weak hardware | Increase `--timeout` value |
| Permission denied | Can't write to outputs | Run as administrator or change output directory |

### 14.4 Final Deliverable

The agent MUST produce:
1. `docs/FOR_SADAF.md` — This document (already provided)
2. A complete structured report (Section 11) at the end of execution
3. All experiment outputs in `outputs/experiments/run_*`
4. A summary of any issues encountered and how they were resolved

### 14.5 Minimum Viable Success Criteria

The experiment is considered successful if:
- All 6 algorithms complete Phase 1 (online simulation) without crashing
- All 6 algorithms complete Phase 2 (offline benchmarks) with >50% success rate
- All output files exist and are non-empty
- metrics_summary.csv contains all 6 algorithm rows
- routing_log.csv contains all 6 algorithm rows
- Plots directory contains all 6 PNG files

If any of these criteria fail, the agent must investigate, fix, and retry.

---

*End of FOR_SADAF.md — AI agent handoff complete.*
