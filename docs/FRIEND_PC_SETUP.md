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
    & "C:\Program Files (x86)\Eclipse\Sumo\bin\sumo.exe" --version
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
pip install -r requirements.txt
```

Optional (for development/testing):
```powershell
pip install -r requirements-dev.txt
```

---

## 6. Run Preflight Check

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
python preflight.py
```

Expected: All checks PASS or OPTIONAL.

---

## 7. Run Complete Thesis Experiment (one command)

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
python run_thesis.py
```

This single command runs:
1. Preflight environment check
2. Pipeline validation (all 6 algorithms)
3. Full experiment (300 steps, 300 vehicles, 6 algorithms) with per-step progress
4. Plot generation (34 figure groups)
5. Final comprehensive summary

On the friend's fast machine, expect ~1-2 hours total.

---

## 8. Regenerate Figures (if experiment already ran)

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
python scripts/generate_all_plots.py
```

To save figures to a specific folder:

```powershell
python scripts/generate_all_plots.py -o C:\Users\SAKIB\Desktop\thesis_figures
```

---

## 9. Run Tests

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
python -m pytest tests/ -v
```

---

## 10. Clean Outputs (if needed)

```powershell
Remove-Item -Recurse -Force "outputs\experiments\*" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "outputs\validation\*" -ErrorAction SilentlyContinue
```
