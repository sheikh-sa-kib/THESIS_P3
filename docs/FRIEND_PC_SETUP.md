# Friend's PC Setup — Copy-Paste Commands

Run these commands in **Windows PowerShell**.

---

```powershell
git clone https://github.com/sheikh-sa-kib/THESIS_P3.git

cd THESIS_P3

python -m venv .venv

Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"

python preflight.py

python run_thesis.py --preset heavy
```

---

## What each step does

| Step | Purpose |
|------|---------|
| `git clone` | Download the repository |
| `cd THESIS_P3` | Enter the project directory |
| `python -m venv .venv` | Create isolated Python environment |
| `Set-ExecutionPolicy` | Allow running activation script (Windows restriction) |
| `.\.venv\Scripts\Activate.ps1` | Activate the virtual environment |
| `pip install -r requirements.txt` | Install runtime dependencies |
| `$env:SUMO_HOME = ...` | Point to SUMO installation |
| `python preflight.py` | Verify environment before experiment |
| `python run_thesis.py --preset heavy` | Run complete thesis experiment (one command) |

## Presets

Use `--preset` to choose the experiment scope:

| Preset | Command | Purpose |
|--------|---------|---------|
| smoke | `run_thesis.py --preset smoke` | Verify installation (~10 s) |
| light | `run_thesis.py --preset light` | Quick laptop comparison (~5–15 min) |
| **heavy** | `run_thesis.py --preset heavy` | **Thesis-quality experiment (~30–90 min)** |
| extreme | `run_thesis.py --preset extreme` | Stress-test (~2–6 hr) |

The `heavy` preset runs: preflight → validation → all 6 algorithms (online SUMO
simulation) → offline benchmarks → CSV generation → 34 publication-ready plots →
final summary. One command, no manual steps.

## Multi-seed runs (optional)

```powershell
python run_thesis.py --preset heavy --seeds 42 43 44
```

---

## Run tests

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
python -m pytest tests/ -v
```

## Clean outputs (if needed)

```powershell
Remove-Item -Recurse -Force "outputs\experiments\*" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "outputs\validation\*" -ErrorAction SilentlyContinue
```

---

## If the experiment is interrupted (shutdown / crash / Ctrl+C)

The experiment checkpoint system **auto-recovers**. Do NOT delete any output files.

```powershell
# Just re-run with --resume — it auto-detects the latest run directory
python run_thesis.py --preset heavy --resume
```

Or specify a specific directory:
```powershell
python run_thesis.py --preset heavy --resume --resume-dir outputs/experiments/run_20260712_095200
```

### What the recovery system does:

| Scenario | Behavior |
|----------|----------|
| **Crash during algorithm #3** | Algorithms #1, #2 are verified complete and skipped. Algorithm #3 restarts from scratch. |
| **Crash during CSV writing** | Incomplete CSVs are detected (wrong row count). All algorithms re-run. |
| **Crash during plot generation** | CSVs are intact. Algorithms skipped. Plots regenerated. |
| **Power failure mid-algorithm** | Same as crash — completed algos are verified and skipped. |
| **Keyboard interrupt (Ctrl+C)** | Same — last completed algo's checkpoint is loaded. |
| **Re-run after full success** | All algos verified, all skipped, CSVs rewritten, plots regenerated. Safe no-op. |

### Recovery guarantees:

- **Never re-runs** an algorithm whose output files (`metrics_summary.csv`,
  `simulation_log.csv`, `.rou.xml`) are verified complete.
- **Checkpoint is written atomically** (temp file + rename) — survives power loss mid-write.
- **Multi-seed safe** — each seed creates its own `run_*` directory independently.
- **Checkpoint is cleared** only after the ENTIRE pipeline (simulation + plots + summary)
  completes successfully.

---

## If SUMO is not installed

Download from https://sumo.dlr.de/download/ — install **SUMO 1.27.1**
(`sumo-1_27_1+setup.exe`). The default install path is `C:\Program Files (x86)\Eclipse\Sumo`.
