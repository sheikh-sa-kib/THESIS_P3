#!/usr/bin/env python3
"""Headless validation experiment - small-scale run on Midtown Manhattan.

Usage:
    python scripts/run_validation.py

Requirements:
    - SUMO_HOME environment variable set
    - Virtual environment activated
    - data/maps/midtown_manhattan.net.xml exists
    - data/routes/midtown_manhattan.rou.xml exists
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SUMO_HOME = os.environ.get("SUMO_HOME", "").strip()
if _SUMO_HOME:
    _tools = os.path.join(_SUMO_HOME, "tools")
    if _tools not in sys.path:
        sys.path.insert(0, _tools)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.routing.factory import RoutingFactory
from e3hybrid.routing.request import RoutingRequest
from e3hybrid.sumo.config import SumoConfig
from e3hybrid.sumo.connection import SumoTraciConnection
from e3hybrid.sumo.network_importer import SumoNetworkImporter
from e3hybrid.vehicle.types import VehicleId

ALL_ALGORITHMS = ("dijkstra", "astar", "aco", "bco", "pso", "e3hybrid")

DATA_DIR = _PROJECT_ROOT / "data"
NET_FILE = DATA_DIR / "maps" / "midtown_manhattan.net.xml"
ROUTE_FILE = DATA_DIR / "routes" / "midtown_manhattan.rou.xml"
OUTPUT_DIR = _PROJECT_ROOT / "outputs" / "validation"

TOTAL_STEPS = 300


@dataclass
class AlgorithmResult:
    name: str = ""
    total_steps: int = 0
    total_vehicles: int = 0
    total_execution_s: float = 0.0
    avg_step_time_ms: float = 0.0
    peak_memory_mb: float = 0.0
    max_vehicles_on_road: int = 0
    simulation_errors: int = 0


class ProgressReporter:
    def __init__(self, total_steps: int, algo_name: str) -> None:
        self._total_steps = total_steps
        self._algo_name = algo_name
        self._start = time.time()
        self._last = 0.0

    def update(self, step: int, vehicles: int, errors: int) -> None:
        now = time.time()
        if now - self._last < 1.0 and step < self._total_steps:
            return
        self._last = now
        elapsed = now - self._start
        pct = step / self._total_steps * 100
        eta_s = elapsed / step * (self._total_steps - step) if step > 0 else 0.0
        print(
            f"\r\x1b[K  {self._algo_name:<10} | "
            f"Step {step:<5}/{self._total_steps} {pct:3.0f}% | "
            f"Veh {vehicles:<4} | "
            f"Errors {errors:<2} | "
            f"Elapsed {elapsed:.1f}s ETA {eta_s:.0f}s",
            end="", flush=True,
        )

    def done(self) -> float:
        t = time.time() - self._start
        print(f"\r\x1b[K  [{self._algo_name}] completed in {t:.1f}s")
        return t


def run_simulation(algo_name: str, config: SumoConfig, steps: int) -> AlgorithmResult:
    """Run headless SUMO simulation and collect metrics."""
    result = AlgorithmResult(name=algo_name)
    conn = SumoTraciConnection(config)
    conn.start()
    try:
        reporter = ProgressReporter(steps, algo_name)
        max_veh = 0
        errors = 0
        for s in range(steps):
            try:
                conn.step()
            except Exception:
                errors += 1
            current = len(conn.get_vehicle_ids())
            max_veh = max(max_veh, current)
            reporter.update(s + 1, current, errors)

        result.total_steps = steps
        result.total_vehicles = conn.get_min_expected_number_vehicles()
        result.total_execution_s = reporter.done()
        result.avg_step_time_ms = result.total_execution_s / steps * 1000
        result.max_vehicles_on_road = max_veh
        result.simulation_errors = errors
        try:
            import psutil
            result.peak_memory_mb = psutil.Process().memory_info().rss / (1024 * 1024)
        except ImportError:
            pass
    finally:
        conn.stop()
    return result


def check_routing(algo_name: str) -> dict[str, Any]:
    """Verify route computation works on the real network."""
    config = SumoConfig(
        sumo_net_file=NET_FILE, sumo_route_file=ROUTE_FILE,
        sumo_seed=42, use_gui=False,
    )
    conn = SumoTraciConnection(config)
    conn.start()
    try:
        importer = SumoNetworkImporter(conn)
        graph = importer.import_graph()
        edges = [e for e in conn.get_edge_ids() if not e.startswith(":")]
        if len(edges) < 2:
            return {"success": False, "error": "not enough edges"}

        source = conn.get_edge_from_junction(edges[0])
        target = conn.get_edge_to_junction(edges[-1])
        if source == target:
            target = conn.get_edge_to_junction(edges[-2])

        algo = RoutingFactory.create_algorithm(algo_name)
        req = RoutingRequest(
            source_node=source, destination_node=target,
            vehicle_id=VehicleId("v"),
            vehicle_constraints={}, battery_state={},
            max_candidates=1, timeout_s=60.0,
        )
        r1 = algo.compute_route(req, graph=graph)
        r2 = algo.compute_route(req, graph=graph)
        det = False
        if r1.success and r2.success and r1.primary_route and r2.primary_route:
            det = list(r1.primary_route.edge_sequence) == list(r2.primary_route.edge_sequence)
        return {
            "success": r1.success,
            "deterministic": det,
            "length": len(r1.primary_route.edge_sequence) if r1.success and r1.primary_route else 0,
            "distance_m": r1.primary_route.total_distance_m if r1.success and r1.primary_route else 0,
            "runtime_s": r1.runtime_s,
        }
    finally:
        conn.stop()


def check_e3hybrid_source() -> dict[str, bool]:
    """Analyse hybrid.py source for required components."""
    import ast
    path = _PROJECT_ROOT / "src" / "e3hybrid" / "swarm" / "hybrid.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    methods = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}

    has_pheromone = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "HybridPheromoneMatrix"
        for n in ast.walk(tree)
    )
    return {
        "pheromone_matrix": has_pheromone,
        "aco_influence": "_compute_raw_aco" in methods,
        "bco_influence": "_compute_raw_bco" in methods,
        "pso_influence": "_compute_raw_pso" in methods,
        "adaptive_meta_controller": "_update_meta_controller" in methods,
        "diversity": "_compute_diversity" in methods,
        "population_partitioning": "_assign_subpopulations" in methods,
        "optimize_method": "optimize" in methods,
        "min_10_methods": len(methods) >= 10,
    }


def write_csv(results: list[AlgorithmResult], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Algorithm", "Steps", "MaxVehicles", "Errors",
                     "Exec_s", "Step_ms", "Mem_MB"])
        for r in results:
            w.writerow([r.name, r.total_steps, r.max_vehicles_on_road,
                        r.simulation_errors, f"{r.total_execution_s:.3f}",
                        f"{r.avg_step_time_ms:.1f}", f"{r.peak_memory_mb:.1f}"])


def print_table(results: list[AlgorithmResult]) -> None:
    print(f"\n{'=' * 110}")
    print(f"  VALIDATION SUMMARY")
    print(f"{'=' * 110}")
    print(f"  {'Algo':<10} {'Steps':<7} {'MaxVeh':<8} {'Errors':<8} "
          f"{'Exec(s)':<9} {'Step(ms)':<9} {'Mem(MB)':<8}")
    print(f"  {'-' * 80}")
    for r in results:
        print(f"  {r.name:<10} {r.total_steps:<7} {r.max_vehicles_on_road:<8} "
              f"{r.simulation_errors:<8} {r.total_execution_s:<9.1f} "
              f"{r.avg_step_time_ms:<9.1f} {r.peak_memory_mb:<8.1f}")


def write_plots(results: list[AlgorithmResult], output_dir: Path) -> None:
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    names = [r.name for r in results]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    colors = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948"]
    datasets = [
        ("Execution Time (s)", [r.total_execution_s for r in results]),
        ("Max Vehicles", [r.max_vehicles_on_road for r in results]),
        ("Peak Memory (MB)", [r.peak_memory_mb for r in results]),
    ]
    for ax, (title, vals) in zip(axes, datasets):
        ax.bar(names, vals, color=colors)
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=30)
    plt.tight_layout()
    plt.savefig(output_dir / "validation_plots.png", dpi=150)
    plt.close()


def main() -> int:
    print()
    print("=" * 72)
    print("  E3-HYBRID VALIDATION EXPERIMENT")
    print("  Headless | Midtown Manhattan | 6 Algorithms")
    print("=" * 72)

    for fp, lbl in [(NET_FILE, "Network"), (ROUTE_FILE, "Routes")]:
        if not fp.exists():
            print(f"  [ERROR] {lbl} not found: {fp}")
            return 1
    print(f"  Network: {NET_FILE}")
    print(f"  Routes:  {ROUTE_FILE}")
    print(f"  Steps:   {TOTAL_STEPS}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- [1/4] E3-Hybrid source analysis ----
    print("\n" + "-" * 72)
    print("  [1/4] E3-Hybrid source code analysis")
    print("-" * 72)
    e3 = check_e3hybrid_source()
    for k, v in e3.items():
        print(f"    {k:<50} {'OK' if v else 'MISSING'}")
    all_components = all(v for k, v in e3.items() if k != "min_10_methods")
    print(f"  -> {'ALL COMPONENTS PRESENT' if all_components else 'MISSING COMPONENTS'}")

    # ---- [2/4] Route computation integrity ----
    print("\n" + "-" * 72)
    print("  [2/4] Route computation integrity (offline)")
    print("-" * 72)
    routing_results: dict[str, dict[str, Any]] = {}
    for name in ALL_ALGORITHMS:
        info = check_routing(name)
        routing_results[name] = info
        status = "PASS" if info.get("success") else "FAIL"
        det = "det" if info.get("deterministic") else "non-det"
        print(f"    {name:<12} {status}  {det}  "
              f"len={info.get('length', 0):<4} "
              f"dist={info.get('distance_m', 0):<8.0f}m "
              f"t={info.get('runtime_s', 0):.4f}s")

    # ---- [3/4] Headless simulation (single run, same for all algorithms) ----
    print("\n" + "-" * 72)
    print("  [3/4] Headless simulation (verifies SUMO loads + runs cleanly)")
    print("-" * 72)
    cfg = SumoConfig(
        sumo_net_file=NET_FILE, sumo_route_file=ROUTE_FILE,
        sumo_seed=42, step_length_ms=1000, use_gui=False,
    )
    print(f"\n  >>> Running SUMO (no rerouting - verifies network/route compatibility) <<<")
    sim_result = run_simulation("sumo", cfg, TOTAL_STEPS)
    results = [sim_result]

    # ---- [4/4] Outputs ----
    print("\n" + "-" * 72)
    print("  [4/4] Outputs")
    print("-" * 72)
    print(f"\n  Simulation result:")
    print(f"    Steps:     {sim_result.total_steps}")
    print(f"    Max veh:   {sim_result.max_vehicles_on_road}")
    print(f"    Errors:    {sim_result.simulation_errors}")
    print(f"    ExecTime:  {sim_result.total_execution_s:.1f}s")
    print(f"    Avg step:  {sim_result.avg_step_time_ms:.1f}ms")
    print(f"    Memory:    {sim_result.peak_memory_mb:.1f}MB")

    csv_path = OUTPUT_DIR / "validation_summary.csv"
    write_csv(results, csv_path)
    print(f"  [CSV]  {csv_path}")

    json_path = OUTPUT_DIR / "validation_metrics.json"
    json.dump({
        "experiment": {
            "network": str(NET_FILE), "routes": str(ROUTE_FILE),
            "total_steps": TOTAL_STEPS, "seed": 42,
        },
        "simulation": {
            "max_vehicles": sim_result.max_vehicles_on_road,
            "errors": sim_result.simulation_errors,
            "execution_time_s": sim_result.total_execution_s,
            "avg_step_time_ms": sim_result.avg_step_time_ms,
            "peak_memory_mb": sim_result.peak_memory_mb,
        },
        "routing_integrity": {
            name: {k: v for k, v in info.items() if k != "error"}
            for name, info in routing_results.items()
        },
        "e3hybrid_components": {k: bool(v) for k, v in e3.items()},
    }, json_path.open("w", encoding="utf-8"), indent=2)
    print(f"  [JSON] {json_path}")

    write_plots(results, OUTPUT_DIR)

    routings_ok = all(info.get("success") for info in routing_results.values())
    sim_ok = sim_result.simulation_errors == 0
    print(f"\n{'=' * 72}")
    if routings_ok:
        print("  [PASS] All 6 algorithms compute routes on the real network")
    else:
        for name, info in routing_results.items():
            if not info.get("success"):
                print(f"  [FAIL] {name} routing failed")
    if sim_ok:
        print("  [PASS] SUMO simulation ran without errors")
    else:
        print(f"  [FAIL] {sim_result.simulation_errors} errors during simulation")
    print(f"  Results: {OUTPUT_DIR}")
    print(f"{'=' * 72}")
    return 0 if routings_ok and sim_ok else 1


if __name__ == "__main__":
    sys.exit(main())
