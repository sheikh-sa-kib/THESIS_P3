#!/usr/bin/env python3
"""Environment preflight checker for the E3-Hybrid thesis experiment.

Usage:
    python preflight.py

Reports PASS / WARNING / FAIL for every prerequisite.
Exits with 0 if all checks pass, 1 if any FAIL.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

_PASS = "PASS"
_WARN = "WARNING"
_FAIL = "FAIL"
_OPT = "OPTIONAL"

_MAX_LABEL = 60

ROOT = Path(__file__).resolve().parent
MIN_RAM_GB = 4.0
MIN_DISK_GB = 5.0
MIN_PYTHON = (3, 12)
SUMO_VERSION_TARGET = "1.27.1"
SUMO_VERSION_MIN = (1, 20, 0)
SUMO_HOME_DEFAULT = Path(r"C:\Program Files (x86)\Eclipse\Sumo")
RUNTIME_PIP_PACKAGES = {
    "yaml": "PyYAML",
    "matplotlib": "matplotlib",
    "psutil": "psutil",
}
SUMO_PACKAGES = {
    "traci": "traci (SUMO interface)",
    "sumolib": "sumolib (SUMO library)",
}
DEV_PACKAGES = {
    "pytest": "pytest (testing)",
}
REQUIRED_FILES = [
    "requirements.txt",
    "requirements-dev.txt",
    "data/maps/midtown_manhattan.net.xml",
    "data/routes/midtown_manhattan.rou.xml",
    "data/configs/midtown_manhattan.sumocfg",
    "src/e3hybrid/__init__.py",
    "scripts/run_experiment.py",
    "scripts/run_validation.py",
    "scripts/generate_all_plots.py",
    "pyproject.toml",
    "VERSION",
]
CHECKED: list[tuple[str, str, str, str]] = []


def _label(text: str) -> str:
    dots = _MAX_LABEL - len(text)
    return text + ("." * max(dots, 1))


def _check(label: str, ok: bool, msg: str = "", section: str = "env") -> str:
    status = _PASS if ok else _FAIL
    CHECKED.append((label, status, msg, section))
    return status


def _warn(label: str, msg: str, section: str = "env") -> str:
    CHECKED.append((label, _WARN, msg, section))
    return _WARN


def _opt(label: str, msg: str, section: str = "env") -> str:
    CHECKED.append((label, _OPT, msg, section))
    return _OPT


def _try_import(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def _get_version(pkg: str) -> str:
    try:
        mod = __import__(pkg)
        v = getattr(mod, "__version__", None)
        if v and v != "0.0.0":
            return v
        import importlib.metadata
        return importlib.metadata.version(pkg)
    except Exception:
        if pkg in ("traci", "sumolib"):
            return _get_sumo_version()
        return "unknown"


def _get_sumo_version() -> str:
    sumo_home = Path(os.environ.get("SUMO_HOME", SUMO_HOME_DEFAULT))
    sumo_exe = sumo_home / "bin" / "sumo.exe"
    if not sumo_exe.exists():
        return "unknown"
    try:
        r = subprocess.run([str(sumo_exe), "--version"],
                           capture_output=True, text=True, timeout=10)
        m = re.search(r"\b(\d+\.\d+\.\d+)\b", r.stdout or r.stderr)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
#  OS
# ---------------------------------------------------------------------------
def check_os() -> None:
    label = "OS"
    if sys.platform == "win32":
        ver = platform.version()
        _check(label, True, f"Windows ({ver})")
    else:
        _warn(label, f"Expected Windows, got {sys.platform}")


# ---------------------------------------------------------------------------
#  Python
# ---------------------------------------------------------------------------
def check_python() -> None:
    v = sys.version_info
    ok = (v.major, v.minor) >= MIN_PYTHON
    _check(
        f"Python {v.major}.{v.minor}.{v.micro}",
        ok,
        f"Requires >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}" if not ok else "",
    )


# ---------------------------------------------------------------------------
#  Git
# ---------------------------------------------------------------------------
def check_git() -> None:
    path = shutil.which("git")
    if path:
        try:
            r = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=10)
            _check("Git", r.returncode == 0, r.stdout.strip() if r.returncode == 0 else "")
            return
        except Exception:
            pass
    _check("Git", False, "git not found on PATH. Install from https://git-scm.com/")


# ---------------------------------------------------------------------------
#  pip
# ---------------------------------------------------------------------------
def check_pip() -> None:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            _check("pip", True, r.stdout.strip())
        else:
            _check("pip", False, "pip not functional: " + r.stderr.strip())
    except Exception as e:
        _check("pip", False, f"pip check failed: {e}. Install Python with pip.")


# ---------------------------------------------------------------------------
#  Virtual environment
# ---------------------------------------------------------------------------
def check_venv() -> None:
    venv = ROOT / ".venv"
    venv_python = venv / "Scripts" / "python.exe"
    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )
    if venv_python.exists() and in_venv:
        _check("Virtual environment .venv", True, "Active", "setup")
    elif venv_python.exists():
        _warn("Virtual environment .venv", "Exists but not active (run `.venv\\Scripts\\Activate.ps1`)", "setup")
    else:
        _check("Virtual environment .venv", False,
               "Not found. Run: python -m venv .venv && .venv\\Scripts\\Activate.ps1",
               "setup")


# ---------------------------------------------------------------------------
#  Python packages
# ---------------------------------------------------------------------------
def check_packages() -> None:
    # Runtime pip packages
    for pkg, desc in RUNTIME_PIP_PACKAGES.items():
        installed = _try_import(pkg)
        if installed:
            ver = _get_version(pkg)
            _check(desc, True, f"{pkg} {ver}", "setup")
        else:
            _check(desc, False, f"{pkg} not installed", "setup")

    # SUMO-bundled packages
    for pkg, desc in SUMO_PACKAGES.items():
        installed = _try_import(pkg)
        if installed:
            ver = _get_version(pkg)
            _check(desc, True, f"{pkg} {ver}", "setup")
        else:
            _check(desc, False, f"{pkg} not importable", "setup")

    # Dev packages (from requirements-dev.txt)
    dev_req = ROOT / "requirements-dev.txt"
    dev_hint = f"Install: pip install -r {dev_req.name}" if dev_req.exists() else "Install for development tools"
    for pkg, desc in DEV_PACKAGES.items():
        installed = _try_import(pkg)
        if installed:
            ver = _get_version(pkg)
            _check(desc, True, f"{pkg} {ver}", "setup")
        else:
            _opt(desc, f"{pkg} not installed. {dev_hint}", "setup")


# ---------------------------------------------------------------------------
#  SUMO installation
# ---------------------------------------------------------------------------
def check_sumo() -> None:
    sumo_home = Path(os.environ.get("SUMO_HOME", SUMO_HOME_DEFAULT))
    sumo_bin = sumo_home / "bin"
    sumo_exe = sumo_bin / "sumo.exe"
    sumo_gui = sumo_bin / "sumo-gui.exe"
    duarouter_exe = sumo_bin / "duarouter.exe"
    netconvert_exe = sumo_bin / "netconvert.exe"
    random_trips = sumo_home / "tools" / "randomTrips.py"

    # SUMO_HOME
    if sumo_home.exists():
        _check("SUMO_HOME directory", True, str(sumo_home), "sumo")
    else:
        _check("SUMO_HOME directory", False,
               f"Not found at {sumo_home}. "
               "Set SUMO_HOME environment variable to your SUMO installation directory.",
               "sumo")
        return

    # sumo.exe
    if sumo_exe.exists():
        try:
            r = subprocess.run([str(sumo_exe), "--version"],
                               capture_output=True, text=True, timeout=10)
            version_line = r.stdout.strip() or r.stderr.strip()
            _check("sumo.exe", True, version_line[:80], "sumo")
            # Version check
            m = re.search(r"(\d+)\.(\d+)\.(\d+)", version_line)
            if m:
                ver = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                if ver < SUMO_VERSION_MIN:
                    _warn(f"SUMO version {m.group(0)}",
                          f"Minimum recommended is {SUMO_VERSION_TARGET}. "
                          f"Some features may not work correctly.",
                          "sumo")
                elif m.group(0) != SUMO_VERSION_TARGET:
                    _warn(f"SUMO version {m.group(0)}",
                          f"Target is {SUMO_VERSION_TARGET} but {m.group(0)} is installed. "
                          f"This may cause minor differences.",
                          "sumo")
        except Exception as e:
            _check("sumo.exe", False, f"Failed to run: {e}", "sumo")
    else:
        _check("sumo.exe", False,
               f"Not found at {sumo_exe}. Reinstall SUMO from https://sumo.dlr.de/download/",
               "sumo")

    # sumo-gui.exe
    if sumo_gui.exists():
        _check("sumo-gui.exe", True, section="sumo")
    else:
        _warn("sumo-gui.exe", "Not found; GUI will not be available. (Headless mode is fine.)", "sumo")

    # duarouter
    if duarouter_exe.exists():
        _check("duarouter.exe", True, section="sumo")
    else:
        _check("duarouter.exe", False,
               f"Not found at {duarouter_exe}. Reinstall SUMO.", "sumo")

    # netconvert
    if netconvert_exe.exists():
        _check("netconvert.exe", True, section="sumo")
    else:
        _check("netconvert.exe", False,
               f"Not found at {netconvert_exe}. Reinstall SUMO.", "sumo")

    # randomTrips.py
    if random_trips.exists():
        _check("randomTrips.py", True, section="sumo")
    else:
        _check("randomTrips.py", False,
               f"Not found at {random_trips}. Reinstall SUMO with tools.", "sumo")

    # SUMO_HOME environment variable
    env_home = os.environ.get("SUMO_HOME", "")
    if env_home:
        _check("SUMO_HOME env var", True, env_home, "sumo")
    else:
        _warn("SUMO_HOME env var",
              f"Not set. Set it: $env:SUMO_HOME = '{SUMO_HOME_DEFAULT}'", "sumo")

    # PATH
    if str(sumo_home) in os.environ.get("PATH", "") or str(sumo_bin) in os.environ.get("PATH", ""):
        _check("SUMO in PATH", True, section="sumo")
    else:
        _warn("SUMO in PATH", f"Neither {sumo_home} nor {sumo_bin} on PATH", "sumo")


# ---------------------------------------------------------------------------
#  traci import
# ---------------------------------------------------------------------------
def check_traci() -> None:
    if _try_import("traci"):
        ver = _get_version("traci")
        _check("traci import", True, f"traci {ver}", "sumo")
    else:
        _check("traci import", False,
               "traci not importable. Ensure SUMO_HOME/tools is on PYTHONPATH", "sumo")


# ---------------------------------------------------------------------------
#  Executables reachable
# ---------------------------------------------------------------------------
def check_sumo_executables() -> None:
    sumo_home = Path(os.environ.get("SUMO_HOME", SUMO_HOME_DEFAULT))
    sumo_bin = sumo_home / "bin"
    for name in ["sumo", "sumo-gui", "duarouter", "netconvert"]:
        exe = sumo_bin / f"{name}.exe"
        if not exe.exists():
            continue
        try:
            r = subprocess.run([str(exe), "--version"],
                               capture_output=True, text=True, timeout=10)
            ok = r.returncode == 0
            line = (r.stdout.strip() or r.stderr.strip())[:60]
            _check(f"{name}.exe reachable", ok, line, "sumo")
        except Exception:
            pass


# ---------------------------------------------------------------------------
#  Java (only if actually required by SUMO or routing tools)
# ---------------------------------------------------------------------------
def check_java() -> None:
    java = shutil.which("java")
    if java:
        try:
            r = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=10)
            ver = (r.stderr or r.stdout).strip().split("\n")[0]
            _opt("Java", f"Found but not required: {ver}")
        except Exception:
            _opt("Java", "Found but not required")
    else:
        _opt("Java", "Not found. Java is NOT required for this experiment.")


# ---------------------------------------------------------------------------
#  Hardware
# ---------------------------------------------------------------------------
def check_hardware() -> None:
    try:
        import psutil
    except ImportError:
        _warn("Hardware checks", "psutil not installed; skipping hardware checks", "hardware")
        return

    # RAM
    ram = psutil.virtual_memory()
    ram_gb = ram.total / (1024 ** 3)
    ok = ram_gb >= MIN_RAM_GB
    _check(f"RAM ({ram_gb:.1f} GB)", ok,
           f"Minimum {MIN_RAM_GB:.0f} GB required" if not ok else "",
           "hardware")

    # Disk
    try:
        disk = psutil.disk_usage(str(ROOT))
        free_gb = disk.free / (1024 ** 3)
        ok = free_gb >= MIN_DISK_GB
        _check(f"Disk space ({free_gb:.1f} GB free)", ok,
               f"Minimum {MIN_DISK_GB:.0f} GB required" if not ok else "",
               "hardware")
    except Exception:
        _warn("Disk space", "Could not determine", "hardware")

    # CPU
    cpu_count = psutil.cpu_count()
    cpu_logical = psutil.cpu_count(logical=True)
    _check(f"CPU cores ({cpu_count} physical / {cpu_logical} logical)", True, section="hardware")

    # Architecture
    arch = platform.machine()
    _check(f"Architecture ({arch})", arch in ("AMD64", "x86_64"), "", "hardware")


# ---------------------------------------------------------------------------
#  Repository structure
# ---------------------------------------------------------------------------
def check_repo() -> None:
    _check("Repository root", ROOT.exists() and ROOT.is_dir(), str(ROOT), "repo")

    for rel in REQUIRED_FILES:
        p = ROOT / rel
        exists = p.exists()
        _check(f"File: {rel}", exists, "", "repo")

    # Outputs directory
    outputs = ROOT / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    _check("outputs/ directory", outputs.is_dir(), str(outputs), "repo")

    # Write permission
    test_file = outputs / ".write_test"
    try:
        test_file.write_text("test")
        test_file.unlink()
        _check("Write permissions", True, section="repo")
    except PermissionError:
        _check("Write permissions", False,
               f"Cannot write to {outputs}. Run as a user with write access.", "repo")

    # Docs directory
    docs = ROOT / "docs"
    if docs.exists():
        doc_count = len(list(docs.rglob("*.md")))
        _check(f"Documentation ({doc_count} .md files)", doc_count > 0, section="repo")
    else:
        _check("Documentation (docs/)", False, "docs/ directory missing", "repo")


# ---------------------------------------------------------------------------
#  Report
# ---------------------------------------------------------------------------
def _print_section(title: str, section: str) -> int:
    section_checks = [(l, s, m) for l, s, m, c in CHECKED if c == section]
    if not section_checks:
        return 0
    print(f"  [{title}]")
    for label, status, msg in section_checks:
        icon = "+" if status == _PASS else ("!" if status == _WARN else ("~" if status == _OPT else "-"))
        left = label.ljust(54)
        detail = f"  {msg}" if msg else ""
        print(f"     {icon}  {left}{detail}")
    print()
    return sum(1 for _, s, _ in section_checks if s == _FAIL)


def _estimate_runtime() -> str:
    try:
        import psutil
        cpu = psutil.cpu_count()
        ram = psutil.virtual_memory().total / (1024 ** 3)
        if cpu >= 8 and ram >= 16:
            return "~25-35 minutes (6 algorithms, 300 steps, 300 vehicles)"
        elif cpu >= 4 and ram >= 8:
            return "~45-60 minutes (6 algorithms, 300 steps, 300 vehicles)"
        else:
            return "~60-90 minutes (6 algorithms, 300 steps, 300 vehicles)"
    except Exception:
        return "~45-90 minutes depending on hardware"


def print_report() -> int:
    print()
    print("=" * 72)
    print("  E3-HYBRID - ENVIRONMENT PREFLIGHT REPORT")
    print("=" * 72)
    print()

    max_label_len = max(len(l) for l, _, _, _ in CHECKED)
    failures = 0
    warnings = 0
    optionals = 0

    for label, status, msg, section in CHECKED:
        padded = label.ljust(max_label_len + 2)
        if status == _PASS:
            print(f"  [{_PASS}]  {padded}{msg}")
        elif status == _WARN:
            print(f"  [{_WARN}]  {padded}{msg}")
            warnings += 1
        elif status == _OPT:
            print(f"  [{_OPT}]  {padded}{msg}")
            optionals += 1
        else:
            print(f"  [{_FAIL}]  {padded}{msg}")
            failures += 1

    print()
    print("-" * 72)
    print(f"  PASS:      {sum(1 for _, s, _, _ in CHECKED if s == _PASS)}")
    print(f"  WARNING:   {warnings}")
    if optionals:
        print(f"  OPTIONAL:  {optionals}")
    print(f"  FAIL:      {failures}")
    print("-" * 72)
    print()

    # -- Categorized summary --
    repo_fails = _print_section("REPOSITORY", "repo")
    env_fails = _print_section("ENVIRONMENT", "env")
    sumo_fails = _print_section("SUMO", "sumo")
    hw_warns = sum(1 for _, s, _, c in CHECKED if c == "hardware" and s in (_WARN, _FAIL))
    _print_section("HARDWARE", "hardware")
    setup_fails = _print_section("SETUP", "setup")

    # Determine which categories failed
    infra_fails = repo_fails + sumo_fails + env_fails + hw_warns

    if failures == 0:
        runtime_est = _estimate_runtime()
        print("  " + "=" * 62)
        print("  THIS COMPUTER IS READY FOR THE COMPLETE THESIS EXPERIMENT")
        print("  " + "=" * 62)
        print()
        print(f"  Estimated runtime:  {runtime_est}")
        print()
        print("  To run the full experiment, execute:")
        print()
        sumo_home = os.environ.get("SUMO_HOME", str(SUMO_HOME_DEFAULT))
        print(f'    $env:SUMO_HOME = "{sumo_home}"')
        print(f'    $env:PYTHONPATH = "src"')
        print(f'    python run_thesis.py')
        print()
        print("  (This runs preflight -> validation -> experiment -> plots -> summary.)")
        print()
        return 0

    # -- Failures present -- identify which areas --
    print("  " + "=" * 62)
    print("  SETUP SUMMARY")
    print("  " + "=" * 62)
    print()

    only_setup_remains = infra_fails == 0 and failures == setup_fails

    if only_setup_remains:
        print("  Repository and infrastructure:  ALL CHECKS PASSED")
        print()
        print("  This repository is valid and complete.")
        print("  Only local environment setup remains.")
        print()
        print("  Install Python packages:")
        print()
        print("    .venv\\Scripts\\Activate.ps1")
        print("    pip install -r requirements.txt")
        print("    pip install -r requirements-dev.txt")
        print()
        runtime_est = _estimate_runtime()
        print(f"  After setup, estimated runtime:  {runtime_est}")
        print()
        print("  Then run:")
        print(f'    python run_thesis.py')
        print()
    else:
        print(f"  Repository:      {'PASS' if repo_fails == 0 else f'{repo_fails} FAIL'}")
        print(f"  Environment:     {'PASS' if env_fails == 0 else f'{env_fails} FAIL'}")
        print(f"  SUMO:            {'PASS' if sumo_fails == 0 else f'{sumo_fails} FAIL'}")
        print(f"  Setup:           {'PASS' if setup_fails == 0 else f'{setup_fails} FAIL'}")
        print(f"  Hardware:        {'PASS' if hw_warns == 0 else f'{hw_warns} WARN'}")
        print()

    # -- Next commands --
    print("  Next steps after resolving issues:")
    print()
    sumo_home = os.environ.get("SUMO_HOME", str(SUMO_HOME_DEFAULT))
    print(f'    $env:SUMO_HOME = "{sumo_home}"')
    print(f'    $env:PYTHONPATH = "src"')
    print(f'    python preflight.py')
    print()

    check_report_path = ROOT / "preflight.py"
    print(f"  Rerun this script to verify: python {check_report_path.name}")
    print()

    return 1 if failures > 0 else 0


def main() -> int:
    check_os()
    check_python()
    check_git()
    check_pip()
    check_venv()
    check_packages()
    check_sumo()
    check_traci()
    check_sumo_executables()
    check_java()
    check_hardware()
    check_repo()
    return print_report()


if __name__ == "__main__":
    sys.exit(main())
