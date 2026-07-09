# Friend's PC Setup — Copy-Paste Commands

Run these commands in **Windows PowerShell** on the friend's Windows PC after cloning.

---

## 1. Clone Repository

```powershell
git clone https://github.com/sheikh-sa-kib/THESIS_P3.git e3hybrid
cd e3hybrid
```

---

## 2. Verify SUMO Installation

```powershell
# Check if SUMO is installed at the expected path
if (Test-Path "C:\Program Files (x86)\Eclipse\Sumo") {
    Write-Host "SUMO found"
    & "C:\Program Files (x86)\Eclipse\Sumo\sumo.exe" --version
} else {
    Write-Host "SUMO NOT FOUND — download from https://sumo.dlr.de/download/"
    Write-Host "Install SUMO 1.27.1 (sumo-1_27_1+setup.exe)"
    Write-Host "REBOOT PowerShell after installation, then run:"
    Write-Host '  $env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"'
}

# Set environment variable (persist for this session)
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
```

---

## 3. Verify Python

```powershell
python --version
```

Expected: `Python 3.12.x` or higher. If missing, install from https://www.python.org/downloads/ (check "Add Python to PATH").

---

## 4. Create Virtual Environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

---

## 5. Install Dependencies

```powershell
python -m pip install --upgrade pip
pip install pyyaml matplotlib psutil pytest pytest-cov
```

---

## 6. Verify Everything Works

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
$env:PYTHONPATH = "src"
python scripts/run_validation.py
```

Expected: All 6 algorithms PASS, SUMO runs with 0 errors.

---

## 7. Run Determinism Tests

```powershell
python -m pytest tests/integration/test_determinism.py -v --tb=short
```

Expected: 4 tests pass.

---

## 8. Run Short Pilot (2 algorithms, ~2 minutes)

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
$env:PYTHONPATH = "src"
python scripts/run_experiment.py --steps 50 --vehicles 30 --algorithms dijkstra,astar --emergency-count 1 --request-count 20
```

---

## 9. Run Complete Thesis Experiment (~1-2 hours)

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
$env:PYTHONPATH = "src"
python scripts/run_experiment.py --steps 300 --vehicles 300 --period 1.0 --seed 42 --algorithms dijkstra,astar,aco,bco,pso,e3hybrid --reroute-interval 10 --emergency-count 3 --request-count 100 --timeout 60.0
```

---

## 10. Regenerate All Figures (after experiment finishes)

```powershell
$env:PYTHONPATH = "src"
python scripts/generate_all_plots.py
```

To save figures to a specific folder:

```powershell
python scripts/generate_all_plots.py -o C:\Users\SAKIB\Desktop\thesis_figures
```

---

## 11. Regenerate All Benchmarks

```powershell
python -m pytest tests/benchmarks/test_benchmarks.py -v
```

---

## 12. Regenerate Reports

```powershell
# Summary tables are in: outputs\experiments\run_*\plots\data\
Get-ChildItem outputs\experiments -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object { Get-ChildItem "$_\plots\data" }
```

---

## 13. Clean Outputs (if needed)

```powershell
Remove-Item -Recurse -Force "outputs\experiments\*" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "outputs\validation\*" -ErrorAction SilentlyContinue
```
