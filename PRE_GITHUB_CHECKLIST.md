# Pre-GitHub Upload Verification Checklist

**Project:** E3-Hybrid — Dynamic EV Routing with Swarm Intelligence
**Purpose:** Verify the repository is clean, deterministic, portable, and complete before pushing to GitHub.
**Instructions:** Go through each item sequentially. Mark `[x]` when verified. If any item fails, fix before uploading.

---

## 1. Source Code

- [ ] **No `__pycache__` directories committed** — Run `git ls-files | findstr __pycache__` (should be empty). The `.gitignore` has `__pycache__/` but verify no cached bytecode is tracked.
- [ ] **No `.pyc` / `.pyo` files committed** — Run `git ls-files "*.pyc" "*.pyo"` (should be empty). Confirmed by `.gitignore` entries `*.py[cod]` and `*.pyc`.
- [ ] **No `.log` files committed** — Run `git ls-files "*.log"` (should be empty). Confirmed by `.gitignore` `*.log`.
- [ ] **No output data committed** — The `outputs/` directory is gitignored. Verify `git ls-files outputs/` is empty.
- [ ] **No temporary/debug scripts committed** — `tmp_*.py` is gitignored. Also check for any `test_manual.py`, `debug_*.py`, `scratch*.py` not in the test suite.
- [ ] **No absolute paths in source code** — Grep for `[A-Z]:\\` (Windows) and `/home/` or `/Users/` (Unix) in all `.py` files under `src/` and `scripts/`. The `REPRODUCIBILITY.md` uses `F:\THESIS_NEW\` (line 25) and backslash paths (lines 73-76) — those must be fixed to forward-slash relative paths.
- [ ] **All imports use relative-to-project paths** — All imports in `src/e3hybrid/` should be relative within the package (e.g., `from .module import X` or `from e3hybrid.module import X`). No `sys.path.insert` or absolute-import hacks.
- [ ] **No hardcoded file paths** — Grep for hardcoded paths like `data/maps/`, `data/routes/`, `data/configs/` — these should come from config objects, not string literals in business logic.

## 2. Configuration

- [ ] **`.gitignore` covers all required patterns** — Current `.gitignore` (lines 1-17) has:
  - ` .venv/` ✅ — virtual environment
  - ` __pycache__/` ✅ — Python cache
  - ` *.py[cod]`, ` *.pyc` ✅ — compiled bytecode
  - ` *.egg-info/` ✅ — package metadata
  - ` .pytest_cache/` ✅ — pytest cache
  - ` .mypy_cache/` ✅ — mypy cache
  - ` .ruff_cache/` ✅ — ruff cache
  - ` .cache/` ✅ — general cache
  - ` outputs/` ✅ — experiment outputs
  - ` htmlcov/`, ` .coverage` ✅ — coverage data
  - ` *.log` ✅ — log files
  - ` trips.*.xml` ✅ — intermediate trip files (covers `trips.trips.xml`)
  - ` tmp_*.py` ✅ — temporary scripts
  - ` .DS_Store`, ` thumbs.db` ✅ — OS metadata
- [ ] **Missing `.gitignore` entries (add these)**:
  - ` .env` — environment/secret files
  - ` .vscode/` — VS Code settings
  - ` .idea/` — JetBrains IDE settings
  - ` results/` — benchmark reporter output directory (note: FINAL_VERIFICATION.md flags `results/` vs `outputs/` inconsistency)
- [ ] **All seeds are explicit (no default-random)** — Every algorithm must accept an explicit `seed` parameter. Verify `SwarmRandom` (in `src/e3hybrid/swarm/random.py`) never falls back to `random.random()` or `time.time()` as seed. Check `RoutingFactory` injects `benchmark_seed` into all algorithms.
- [ ] **All paths are relative (no `C:\` or `/home/`)** — Grep `src/` and `scripts/` for `[A-Z]:\\` and `/home/` and `/Users/`. The `REPRODUCIBILITY.md` doc itself contains `F:\THESIS_NEW\` (line 25) which must be changed to a relative reference (e.g., `../`) before publishing.
- [ ] **`SUMO_HOME` is discovered at runtime, not hardcoded** — Verify `src/e3hybrid/sumo/` uses `os.environ.get("SUMO_HOME")` or `shutil.which("sumo")` rather than a hardcoded install path. Check for any string like `C:\Program Files\SUMO` in the source.

## 3. Experiments

- [ ] **`run_validation.py` works and all 6 algorithms pass** — Run from project root:
      ```
      python scripts/run_validation.py
      ```
      Verify output shows all 6 algorithms (Dijkstra, A*, ACO, BCO, PSO, E3-Hybrid) with PASS status.
- [ ] **`run_experiment.py` has complete `--help`** — Run:
      ```
      python scripts/run_experiment.py --help
      ```
      Verify it lists: `--steps`, `--vehicles`, `--period`, `--seed`, `--algorithms`, `--reroute-interval`, `--emergency-count`, `--request-count`, `--timeout`.
- [ ] **Every experiment outputs a timestamped directory with all metrics** — Run a short experiment and verify `outputs/experiments/run_YYYYMMDD_HHMMSS/` contains:
  - ` config_snapshot.yaml`
  - ` git_commit.txt`
  - ` environment.json`
  - ` network_metadata.json`
  - ` metrics_summary.csv`
  - ` simulation_log.csv`
  - ` routing_log.csv`
  - ` plots/` with 6 PNG files
- [ ] **Teleportation is detected and reported** — FINAL_VERIFICATION.md (item 7, line 161) notes teleport count is never read from SUMO. Verify `run_experiment.py` step loop calls `traci.simulation.getTeleportNumber()` (or equivalent) and logs it. If missing, this is a pre-upload fix.
- [ ] **No experiment must be rerun due to missing data** — Verify all output fields documented in the schema (REPRODUCIBILITY.md §10) are actually written. Check `completed_trips`, `failed_trips`, `teleports` columns exist and are populated in CSVs.

## 4. Documentation

- [ ] **`docs/algorithms/` contains all 7 files** — Verify:
  - [ ] `ACO.md`
  - [ ] `ASTAR.md`
  - [ ] `BCO.md`
  - [ ] `DIJKSTRA.md`
  - [ ] `E3_HYBRID.md`
  - [ ] `PSO.md`
  - [ ] `SIMULATION_VALIDATION.md`
  - *Confirmed: all 7 present.*
- [ ] **`docs/REPRODUCIBILITY.md` exists** — Verifies software requirements, source code layout, network/route files, seeds, algorithm parameters, output schema, and deterministic replay procedure. **FIX NEEDED**: Replace Windows backslash paths (lines 73-76, `data\maps\...`, `data\routes\...`) with forward-slash paths (`data/maps/...`).
- [ ] **`docs/FINAL_VERIFICATION.md` exists** — Complete audit covering 11 categories with verified items, issues found, and limitations. References known bugs (e.g., `benchmark_runner.py:220-226`).
- [ ] **Every README or doc references project-relative paths** — Grep all `.md` files for `[A-Z]:\\` and `C:\` patterns. Fix any absolute paths to use relative (e.g., `../src/e3hybrid/` instead of `F:\THESIS_NEW\src\e3hybrid\`).
- [ ] **`README.md` exists at project root** — FINAL_VERIFICATION.md (item 3, line 60) notes `README.md` is referenced by `pyproject.toml:10` but is missing. Verify `F:\THESIS_NEW\README.md` exists and has content (the file listing shows it exists).

## 5. Determinism

- [ ] **`SwarmRandom` uses SHA256-based stream derivation (not `hash()`)** — Verify in `src/e3hybrid/swarm/random.py`:
  - Uses `hashlib.sha256` (or similar cryptographic hash) for stream splitting
  - Does NOT use Python's built-in `hash()` which is salted per process start
  - Seeds are derived deterministically from the algorithm `seed` parameter
- [ ] **Same seed + same config = same results** — Run twice:
      ```
      python scripts/run_experiment.py --seed 42 --steps 50 --vehicles 10 --algorithms dijkstra --timeout 60
      python scripts/run_experiment.py --seed 42 --steps 50 --vehicles 10 --algorithms dijkstra --timeout 60
      ```
      Then diff the output CSVs: `git diff outputs/experiments/run_*/metrics_summary.csv` (should be identical within machine tolerance).
- [ ] **No global random state used by any algorithm** — Grep for `random.random()`, `random.randint()`, `random.choice()`, `random.shuffle()` in all files under `src/e3hybrid/swarm/` and `src/e3hybrid/routing/`. All randomness must go through `SwarmRandom` instances, not the global `random` module.
- [ ] **Deterministic replay verification passes** — Run:
      ```
      pytest tests/integration/test_determinism.py -v
      ```
      Verify all `RoutingVerifier.verify_deterministic_replay()` tests pass.

## 6. Build/Run

- [ ] **Python 3.11+ compatible** — Check `pyproject.toml` for `requires-python = ">=3.11"` or `>=3.12`. Note: REPRODUCIBILITY.md specifies `>=3.12`, FINAL_VERIFICATION.md says `>=3.12`. Decide on one minimum version and be consistent.
- [ ] **Dependencies listed** — Check `pyproject.toml` for `[project.dependencies]` and `[project.optional-dependencies]`. Verify all imports used in the codebase are declared (traci, sumolib, PyYAML, matplotlib, psutil, pytest, etc.).
- [ ] **SUMO 1.27.1 required** — REPRODUCIBILITY.md specifies SUMO 1.27.1. Verify `SumoTraciConnection` handles version negotiation gracefully.
- [ ] **No external services required** — Verify no HTTP requests, API calls, or database connections in the codebase. Grep for `requests.get`, `urllib`, `socket`, `http.client` outside of test mocking.
- [ ] **Runs completely offline (no API calls)** — Disconnect network and run:
      ```
      python scripts/run_validation.py
      ```
      Should complete without connection errors. Verify no telemetry, analytics, or update checks are baked in.

## 7. Platform

- [ ] **No Windows-specific paths in code** — Grep `src/` for backslash path separators (`\\` in string literals), `os.sep` usage, `os.path.join("foo", "bar")` where forward-slash constants would work. Use `pathlib.Path` throughout (confirmed by FINAL_VERIFICATION.md, but spot-check).
- [ ] **No Unix-specific assumptions** — Grep for `os.fork()`, `pty`, `signal.SIGKILL`, `/tmp/`, `/dev/null`, `/proc/`, `os.uname()`. Check that `multiprocessing` and `subprocess` usage is cross-platform.
- [ ] **SUMO binary discovered via `PATH` or `SUMO_HOME`** — Verify `SumoTraciConnection` (or the SUMO launcher) uses:
  1. `shutil.which("sumo")` to find SUMO on PATH, then
  2. Falls back to `os.environ.get("SUMO_HOME")`
  3. Never hardcodes an install path
  - Check `src/e3hybrid/sumo/connection.py` or `src/e3hybrid/sumo/simulation.py` for this logic.
- [ ] **`libsumo` fallback works cross-platform** — FINAL_VERIFICATION.md notes `use_libsumo=True` by default, falling back to `traci` on `ImportError`. Verify this fallback handles both Windows (where libsumo is experimental) and Linux.

## Summary of Known Pre-Upload Fixes Required

| # | File/Area | Issue | Action |
|---|-----------|-------|--------|
| 1 | `.gitignore` | Missing `.env`, `.vscode/`, `.idea/`, `results/` | Add these patterns |
| 2 | `docs/REPRODUCIBILITY.md:25,73-76` | Windows absolute path `F:\THESIS_NEW\` and backslash paths | Replace with relative forward-slash paths |
| 3 | `src/e3hybrid/swarm/random.py` | Verify SHA256-based stream derivation (not `hash()`) | Audit and fix if needed |
| 4 | `scripts/run_experiment.py` | Teleport count, completed/failed trips not collected | Add `traci.simulation.getTeleportNumber()`, trip tracking |
| 5 | `src/e3hybrid/routing/benchmark_runner.py:220-226` | `AttributeError` on `result.statistics` when `result is None` | Fix the error handling path |
| 6 | `src/e3hybrid.egg-info/` directory | Package metadata directory tracked or present in repo | Ensure gitignored and removed from tracking |

## Final Pre-Push Commands

```bash
# 1. Check nothing unwanted is tracked
git status
git ls-files --others --exclude-standard

# 2. Verify no secrets or credentials
git diff --cached --check

# 3. Run the test suite
pytest -v

# 4. Run validation
python scripts/run_validation.py

# 5. Verify determinism
pytest tests/integration/test_determinism.py -v

# 6. Dry-run the experiment (short)
python scripts/run_experiment.py --seed 42 --steps 20 --vehicles 5 --algorithms dijkstra --timeout 30

# 7. Check for any remaining absolute paths
rg '[A-Z]:\\' src/ scripts/ docs/ --type md --type py

# 8. Final git diff review
git diff --stat
```

---
*Generated: 2026-07-09*
*Delete this checklist after all items are verified.*
