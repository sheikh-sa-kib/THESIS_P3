# Full Thesis Simulation Plan

This document describes how to produce all figures, tables, and results for the thesis paper: *"E3-Hybrid: An Event-driven, Energy-aware, and Emergent-responsive Hybrid Routing Framework"*.

---

## Overview

**Setting:** Urban traffic grid (10×10), ~17 km²  
**Duration:** 300 simulation steps (~5 minutes at 1 step/sec)  
**Demand:** 300 vehicles, Poisson arrival (period = 1.0)  
**Algorithms:** 6 (dijkstra, astar, aco, bco, pso, e3hybrid)  
**Emergencies:** 3 vehicles rerouted at step 50  
**Demand requests:** 100 vehicles adaptively routed en-route  

---

## Step by Step

### Step 1: Set up environment

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
$env:PYTHONPATH = "src"
```

### Step 2: Run experiment

```powershell
cd \path\to\e3hybrid
.venv\Scripts\Activate.ps1
python scripts/run_experiment.py `
    --steps 300 --vehicles 300 --period 1.0 `
    --seed 42 `
    --algorithms dijkstra,astar,aco,bco,pso,e3hybrid `
    --reroute-interval 10 --emergency-count 3 --request-count 100 `
    --timeout 60.0
```

**Estimated time:** 1–2 hours on a modern PC (8+ cores, 16+ GB RAM).

### Step 3: Generate figures

```powershell
python scripts/generate_all_plots.py
```

Output:
- `outputs/experiments/run_YYYYMMDD_HHMMSS/plots/png/*.png` (34 figures)
- `outputs/experiments/run_YYYYMMDD_HHMMSS/plots/pdf/*.pdf` (34 figures)
- `outputs/experiments/run_YYYYMMDD_HHMMSS/plots/data/*.csv` (summary tables)

### Step 4: Copy outputs to thesis

```powershell
python scripts/copy_to_thesis.py --paper-dir "C:\Users\SAKIB\Desktop\thesis_paper\figures"
```

This copies:
- PDFs (vector) for publication-quality figures
- CSVs (summary metrics) for table generation
- Key PNGs for quick reference

### Step 5: Run benchmarks (optional)

```powershell
python -m pytest tests/benchmarks/test_benchmarks.py -v
```

### Step 6: Run all tests

```powershell
python -m pytest tests/ -v
```

---

## Expected Outputs

### Primary metrics (for Table 1 in paper)

| Metric | Per algorithm |
|--------|---------------|
| Avg travel time | seconds |
| Avg speed | m/s |
| Throughput | vehicles delivered |
| Congestion | % edges near capacity |
| Emergency events | count |
| Teleports | count |
| Execution time | seconds |
| Peak memory | MB |
| Reroutes triggered | count |

### Figures (for paper)

| Figure | Type | Shows |
|--------|------|-------|
| 1 | Bar chart | Cross-algorithm comparison (all metrics) |
| 2 | Line chart | Time-series: active vehicles, congestion |
| 3 | Boxplot/Violin | Travel time distribution |
| 4 | Histogram/CDF | Speed & travel time distributions |
| 5 | Scatter | Speed vs travel time correlation |
| 6 | Heatmap | Congestion over time |
| 7 | Dashboard | Composite summary |

---

## Output Directory Layout

```
outputs/experiments/run_YYYYMMDD_HHMMSS/
├── config_snapshot.yaml      # Experiment config
├── environment.json          # Hardware/OS info
├── metrics_summary.csv       # Per-algorithm metrics
├── simulation_log.csv        # Step-by-step log (all algos)
├── routing_log.csv           # Routing benchmark results
├── algorithm_timing.csv      # Per-algorithm timing
├── emergency_log.csv         # Emergency event log
├── network_metadata.json     # Network topology info
├── git_commit.txt            # Reproducibility hash
├── *.rou.xml                 # Route files per algorithm
├── plots/
│   ├── png/                  # 34 PNG figures
│   ├── pdf/                  # 34 PDF (vector) figures
│   └── data/                 # Summary CSVs for tables
```

---

## Reproducibility

The combination of:
1. **Fixed seed** (`--seed 42`)
2. **Deterministic algorithms** (verified by `test_determinism.py`)
3. **Configuration snapshot** (`config_snapshot.yaml`)
4. **Environment metadata** (`environment.json`)
5. **Git commit hash** (`git_commit.txt`)

guarantees that re-running with the same parameters produces identical results.
