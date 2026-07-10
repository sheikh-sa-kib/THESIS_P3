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

python run_thesis.py
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
| `python run_thesis.py` | Run everything: validation → experiment → plots → summary |

---

## After experiment finishes — regenerate figures

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
python scripts/generate_all_plots.py -o C:\Users\SAKIB\Desktop\thesis_figures
```

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

## If SUMO is not installed

Download from https://sumo.dlr.de/download/ — install **SUMO 1.27.1**
(`sumo-1_27_1+setup.exe`). The default install path is `C:\Program Files (x86)\Eclipse\Sumo`.
