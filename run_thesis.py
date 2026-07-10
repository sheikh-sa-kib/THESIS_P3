#!/usr/bin/env python3
"""Complete thesis experiment launcher — one command.

Usage:
    python run_thesis.py

Automatically:
  1.  Environment preflight check
  2.  Pipeline validation (all 6 algorithms)
  3.  Full experiment with per-step live progress
  4.  Offline routing benchmarks
  5.  Plot generation (34 figures)
  6.  Final comprehensive summary
"""

from __future__ import annotations

import csv
import json
import os
import platform
import random
import re
import subprocess
import sys
import time
import tracemalloc
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# -- Ensure project modules are importable --------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

_SUMO_HOME = os.environ.get("SUMO_HOME", "").strip()
if _SUMO_HOME:
    _tools = os.path.join(_SUMO_HOME, "tools")
    if _tools not in sys.path:
        sys.path.insert(0, _tools)

try:
    import yaml
except ImportError:
    yaml = None

# -- Project paths --------------------------------------------------------
ALL_ALGORITHMS = ("dijkstra", "astar", "aco", "bco", "pso", "e3hybrid")
DATA_DIR = _PROJECT_ROOT / "data"
NET_FILE = DATA_DIR / "maps" / "midtown_manhattan.net.xml"
ROUTE_FILE = DATA_DIR / "routes" / "midtown_manhattan.rou.xml"
OUTPUT_ROOT = _PROJECT_ROOT / "outputs" / "experiments"

# -- Imports (lazy to allow early preflight even without deps) ------------
def _imports() -> None:
    global RoutingFactory, RoutingRequest, MutableEdgeState, EdgeId
    global SumoConfig, SumoTraciConnection, SumoNetworkImporter, VehicleId
    global ExperimentConfig, StepMetrics, AlgorithmResult
    from e3hybrid.routing.factory import RoutingFactory
    from e3hybrid.routing.request import RoutingRequest
    from e3hybrid.network.edge import MutableEdgeState
    from e3hybrid.network.types import EdgeId
    from e3hybrid.sumo.config import SumoConfig
    from e3hybrid.sumo.connection import SumoTraciConnection
    from e3hybrid.sumo.network_importer import SumoNetworkImporter
    from e3hybrid.vehicle.types import VehicleId

    @dataclass
    class ExperimentConfig:
        steps: int = 300
        vehicles: int = 300
        departure_period: float = 1.0
        seed: int = 42
        algorithms: tuple[str, ...] = ALL_ALGORITHMS
        reroute_interval: int = 10
        emergency_count: int = 3

    @dataclass
    class StepMetrics:
        step: int
        active_vehicles: int
        total_reroutes: int
        emergency_events: int
        blocked_edges: int
        congestion_edges: int
        avg_speed_mps: float = 0.0
        completed_trips: int = 0
        failed_trips: int = 0
        teleport_count: int = 0
        travel_time_s: float = 0.0
        reroute_latency_ms: float = 0.0

    @dataclass
    class AlgorithmResult:
        algo: str = ""
        total_steps: int = 0
        total_vehicles: int = 0
        total_reroutes: int = 0
        emergency_events: int = 0
        max_congestion_edges: int = 0
        max_blocked_edges: int = 0
        avg_travel_time_s: float = 0.0
        avg_waiting_time_s: float = 0.0
        avg_route_length_edges: int = 0
        avg_speed_mps: float = 0.0
        throughput: int = 0
        completed_trips: int = 0
        failed_trips: int = 0
        teleport_count: int = 0
        avg_rerouting_latency_ms: float = 0.0
        total_execution_s: float = 0.0
        peak_memory_mb: float = 0.0
        step_log: list[StepMetrics] = field(default_factory=list)


# ===================================================================
#  SECTION 1 – Environment preflight
# ===================================================================
def run_preflight() -> int:
    print()
    print("=" * 72)
    print("  [1/5] ENVIRONMENT PREFLIGHT")
    print("=" * 72)

    result = subprocess.run(
        [sys.executable, str(_PROJECT_ROOT / "preflight.py")],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if result.returncode != 0:
        print("  [FAIL] Environment preflight failed. Fix issues and re-run.")
        return 1

    print("  [PASS] All preflight checks passed.")
    return 0


# ===================================================================
#  SECTION 2 – Validation
# ===================================================================
def run_validation() -> int:
    print()
    print("=" * 72)
    print("  [2/5] PIPELINE VALIDATION")
    print("=" * 72)

    result = subprocess.run(
        [sys.executable, str(_PROJECT_ROOT / "scripts" / "run_validation.py")],
        capture_output=True, text=True,
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if result.returncode != 0:
        print("  [WARN] Validation had failures. Check output above.")
        print("  The experiment will continue, but results may be affected.")
        return 1
    return 0


# ===================================================================
#  SECTION 3 – Full experiment
# ===================================================================
def generate_routes(net_file: Path, route_file: Path, vehicles: int, period: float, seed: int) -> None:
    sumo_home = os.environ.get("SUMO_HOME", "")
    random_trips = os.path.join(sumo_home, "tools", "randomTrips.py")
    end_time = vehicles * period
    subprocess.run([
        sys.executable, random_trips,
        "-n", str(net_file),
        "-r", str(route_file),
        "--end", str(end_time),
        "--period", str(period),
        "--seed", str(seed),
        "--random-routing-factor", "1.0",
    ], check=True, capture_output=True)


def simulate_algorithm(
    algo_name: str,
    config: ExperimentConfig,
    output_dir: Path,
    algo_idx: int,
    algo_total: int,
    t_exp_start: float,
) -> AlgorithmResult:
    _imports()
    result = AlgorithmResult(algo=algo_name)
    route_file = output_dir / f"{algo_name}.rou.xml"

    if not route_file.exists():
        print(f"    Generating routes for {algo_name}...", flush=True)
        generate_routes(NET_FILE, route_file, config.vehicles, config.departure_period, config.seed)

    sumo_cfg = SumoConfig(
        sumo_net_file=NET_FILE,
        sumo_route_file=route_file,
        sumo_seed=config.seed,
        step_length_ms=1000,
        reroute_interval_steps=config.reroute_interval,
        use_gui=False,
        use_libsumo=True,
        algorithm_names=(algo_name,),
        algorithm_split=((algo_name, 1.0),),
    )

    conn = SumoTraciConnection(sumo_cfg)
    tracemalloc.start()
    t_start = time.perf_counter()

    conn.start()
    try:
        importer = SumoNetworkImporter(conn)
        graph = importer.import_graph()
        algo = RoutingFactory.create_algorithm(algo_name)

        total_reroutes = 0
        total_emergency = 0
        total_teleports = 0
        completed = 0
        failed = 0
        reroute_latencies = []
        step_log = []
        travel_times = []

        # Emergency schedule
        active_emergencies: dict[int, dict] = {}
        emergency_schedule: list[tuple[int, list[str], int]] = []
        if config.emergency_count > 0:
            emerg_rng = random.Random(config.seed + 2000)
            all_edge_ids = [e for e in conn.get_edge_ids() if not e.startswith(":")]
            if len(all_edge_ids) >= 3:
                pool = emerg_rng.sample(
                    all_edge_ids,
                    min(config.emergency_count * 3, len(all_edge_ids)),
                )
                for i in range(config.emergency_count):
                    start_step = emerg_rng.randint(30, max(60, config.steps // 4))
                    affected = [pool[(i * 3 + j) % len(pool)] for j in range(3)]
                    duration = 20
                    emergency_schedule.append((start_step, affected, duration))

        last_progress = 0.0
        progress_interval = max(1, config.steps // 40)

        for s in range(config.steps):
            conn.step()

            # Emergency activation / resolution
            for start_step, affected_edges, duration in emergency_schedule:
                if s == start_step:
                    for eid_str in affected_edges:
                        eid = EdgeId(eid_str)
                        if graph.has_edge(eid):
                            edge = graph.get_edge(eid)
                            new_state = MutableEdgeState(
                                is_blocked=False,
                                current_speed_mps=edge.state.current_speed_mps,
                                travel_time_override_s=edge.state.travel_time_override_s,
                                congestion_factor=edge.state.congestion_factor,
                                hazard_penalty_s=edge.state.hazard_penalty_s,
                                emergency_penalty_s=edge.state.emergency_penalty_s + 120.0,
                                communication_penalty_s=edge.state.communication_penalty_s,
                            )
                            graph.update_edge_state(eid, new_state)
                    total_emergency += 1
                    active_emergencies[start_step] = {
                        "edges": affected_edges,
                        "resolve_step": s + duration,
                    }
            for key in list(active_emergencies.keys()):
                if s >= active_emergencies[key]["resolve_step"]:
                    for eid_str in active_emergencies[key]["edges"]:
                        eid = EdgeId(eid_str)
                        if graph.has_edge(eid):
                            edge = graph.get_edge(eid)
                            restored = max(0.0, edge.state.emergency_penalty_s - 120.0)
                            new_state = MutableEdgeState(
                                is_blocked=edge.state.is_blocked,
                                current_speed_mps=edge.state.current_speed_mps,
                                travel_time_override_s=edge.state.travel_time_override_s,
                                congestion_factor=edge.state.congestion_factor,
                                hazard_penalty_s=edge.state.hazard_penalty_s,
                                emergency_penalty_s=restored,
                                communication_penalty_s=edge.state.communication_penalty_s,
                            )
                            graph.update_edge_state(eid, new_state)
                    del active_emergencies[key]

            vehicles = conn.get_vehicle_ids()
            active = len(vehicles)
            total_teleports += conn.get_teleport_count()
            completed += conn.get_arrived_count()

            congestion = 0
            blocked = 0
            total_speed = 0.0
            speed_count = 0
            for eid in conn.get_edge_ids():
                if eid.startswith(":"):
                    continue
                occ = conn.get_edge_occupancy(eid)
                if occ > 0.8:
                    congestion += 1
                if occ > 0.95:
                    blocked += 1
                spd = conn.get_edge_mean_speed(eid)
                if spd > 0:
                    total_speed += spd
                    speed_count += 1
            avg_speed = total_speed / speed_count if speed_count else 0.0

            step_reroute_latencies = []
            if s > 0 and s % config.reroute_interval == 0:
                for vid in vehicles:
                    t0 = time.perf_counter()
                    try:
                        route_edges = conn.get_vehicle_route(vid)
                        if len(route_edges) < 2:
                            continue
                        pos = conn.get_vehicle_position(vid)
                        _, _, current_edge = pos
                        src = conn.get_edge_to_junction(current_edge) if current_edge else ""
                        dst = conn.get_edge_to_junction(route_edges[-1])
                        if not src or not dst:
                            continue
                        req = RoutingRequest(
                            source_node=str(src),
                            destination_node=str(dst),
                            vehicle_id=VehicleId(vid),
                            vehicle_constraints={},
                            battery_state={},
                            max_candidates=1,
                            timeout_s=30.0,
                            metadata={"source_edge_id": current_edge},
                        )
                        r = algo.compute_route(req, graph=graph)
                        lat = (time.perf_counter() - t0) * 1000
                        reroute_latencies.append(lat)
                        step_reroute_latencies.append(lat)
                        if r.success and r.primary_route:
                            algo_edges = [str(eid) for eid in r.primary_route.edge_sequence]
                            full_route = [current_edge] + algo_edges
                            # Validate lane-level connections before applying
                            valid = True
                            for i in range(len(full_route) - 1):
                                e1, e2 = full_route[i], full_route[i + 1]
                                if e1.startswith(":") or e2.startswith(":"):
                                    continue
                                if not conn.has_lane_connection(e1, e2):
                                    valid = False
                                    break
                            if valid:
                                conn.set_vehicle_route(vid, full_route)
                                total_reroutes += 1
                    except Exception:
                        pass

            step_travel_times = []
            for vid in vehicles:
                try:
                    pos_edge = conn.get_vehicle_position(vid)[2]
                    tt = conn.get_edge_travel_time(pos_edge)
                    travel_times.append(tt)
                    step_travel_times.append(tt)
                except Exception:
                    pass

            step_log.append(StepMetrics(
                step=s,
                active_vehicles=active,
                total_reroutes=total_reroutes,
                emergency_events=total_emergency,
                blocked_edges=blocked,
                congestion_edges=congestion,
                avg_speed_mps=avg_speed,
                completed_trips=completed,
                failed_trips=failed,
                teleport_count=total_teleports,
                travel_time_s=sum(step_travel_times) / len(step_travel_times) if step_travel_times else 0.0,
                reroute_latency_ms=sum(step_reroute_latencies) / len(step_reroute_latencies) if step_reroute_latencies else 0.0,
            ))

            # Live progress output
            pct = (s + 1) / config.steps * 100
            if pct - last_progress >= 2.5 or s == 0 or s == config.steps - 1:
                last_progress = pct
                elapsed = time.perf_counter() - t_start
                elapsed_exp = time.perf_counter() - t_exp_start
                speed_per_step = elapsed / (s + 1)
                remaining_steps = config.steps - (s + 1)
                eta = speed_per_step * remaining_steps
                total_eta = speed_per_step * (config.steps - (s + 1) +
                                              sum(config.steps for _ in range(algo_total - algo_idx)))

                line = (
                    f"  [{algo_idx}/{algo_total}] {algo_name:>10} "
                    f"| step {s+1:>4}/{config.steps} ({pct:>5.1f}%)"
                    f" | elapsed {selfmt(elapsed):>8}"
                    f" | eta {selfmt(eta):>8}"
                    f" | veh {active:>3} arr {completed:>3}"
                    f" | tel {total_teleports:>2} em {total_emergency:>2}"
                    f" | rer {total_reroutes:>3}"
                )
                print(line, flush=True)

    except Exception:
        conn.stop()
        raise

    t_end = time.perf_counter()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    result.total_steps = config.steps
    result.total_vehicles = config.vehicles
    result.total_reroutes = total_reroutes
    result.emergency_events = total_emergency
    result.max_congestion_edges = max(s.congestion_edges for s in step_log) if step_log else 0
    result.max_blocked_edges = max(s.blocked_edges for s in step_log) if step_log else 0
    result.avg_travel_time_s = sum(travel_times) / len(travel_times) if travel_times else 0.0
    result.avg_speed_mps = sum(s.avg_speed_mps for s in step_log) / len(step_log) if step_log else 0.0
    result.throughput = completed
    result.completed_trips = completed
    result.failed_trips = failed
    result.teleport_count = total_teleports
    result.avg_rerouting_latency_ms = sum(reroute_latencies) / len(reroute_latencies) if reroute_latencies else 0.0
    result.total_execution_s = t_end - t_start
    result.peak_memory_mb = peak / (1024 * 1024)
    result.step_log = step_log

    conn.stop()
    return result


def selfmt(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def collect_environment() -> dict[str, Any]:
    env: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "platform": sys.platform,
        "packages": {},
        "sumo_version": "unknown",
    }
    try:
        import traci
        env["sumo_version"] = getattr(traci, "__version__", "unknown")
    except ImportError:
        pass
    try:
        import pkg_resources
        for dist in pkg_resources.working_set:
            if dist.key in ("traci", "sumolib", "PyYAML", "matplotlib", "e3hybrid", "psutil"):
                env["packages"][dist.key] = dist.version
    except Exception:
        pass
    try:
        import psutil
        env["cpu_count"] = psutil.cpu_count()
        env["memory_gb"] = round(psutil.virtual_memory().total / (1024**3), 2)
    except ImportError:
        pass
    return env


def get_git_commit() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"],
                           capture_output=True, text=True, cwd=_PROJECT_ROOT)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return "unversioned"


def _get_git_tag() -> str:
    try:
        r = subprocess.run(["git", "describe", "--tags", "--exact-match"],
                           capture_output=True, text=True, cwd=_PROJECT_ROOT)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return "unversioned"


def write_step_csv(all_step_logs: dict[str, list], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["algorithm", "step", "active_vehicles", "reroutes",
                     "emergency_events", "blocked_edges", "congestion_edges",
                     "avg_speed_mps", "completed_trips", "failed_trips",
                     "teleport_count", "travel_time_s", "reroute_latency_ms"])
        for algo_name, steps in all_step_logs.items():
            for s in steps:
                w.writerow([algo_name, s.step, s.active_vehicles, s.total_reroutes,
                           s.emergency_events, s.blocked_edges, s.congestion_edges,
                           f"{s.avg_speed_mps:.3f}", s.completed_trips, s.failed_trips,
                           s.teleport_count, f"{s.travel_time_s:.3f}",
                           f"{s.reroute_latency_ms:.3f}"])


def write_metrics_csv(results: list, path: Path) -> None:
    fieldnames = [
        "algorithm", "total_steps", "total_vehicles", "total_reroutes",
        "emergency_events", "max_congestion_edges", "max_blocked_edges",
        "avg_travel_time_s", "avg_speed_mps", "throughput", "completed_trips",
        "failed_trips", "teleport_count", "avg_rerouting_latency_ms",
        "total_execution_s", "peak_memory_mb",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(fieldnames)
        for r in results:
            w.writerow([
                r.algo, r.total_steps, r.total_vehicles, r.total_reroutes,
                r.emergency_events, r.max_congestion_edges, r.max_blocked_edges,
                f"{r.avg_travel_time_s:.3f}", f"{r.avg_speed_mps:.3f}",
                r.throughput, r.completed_trips, r.failed_trips,
                r.teleport_count, f"{r.avg_rerouting_latency_ms:.3f}",
                f"{r.total_execution_s:.3f}", f"{r.peak_memory_mb:.3f}",
            ])


def write_network_metadata(conn, path: Path) -> None:
    edges = [e for e in conn.get_edge_ids() if not e.startswith(":")]
    junctions = conn.get_junction_ids()
    meta = {
        "total_edges": len(edges),
        "total_junctions": len(junctions),
        "source_file": str(NET_FILE),
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def run_offline_benchmarks(
    algo_names: tuple[str, ...],
    num_requests: int,
    seed: int,
    timeout_s: float,
    output_dir: Path,
) -> dict[str, dict[str, Any]]:
    _imports()
    results: dict[str, dict[str, Any]] = {}
    sumo_cfg = SumoConfig(
        sumo_net_file=NET_FILE,
        sumo_route_file=ROUTE_FILE,
        sumo_seed=seed,
        step_length_ms=1000,
        use_gui=False,
    )
    conn = SumoTraciConnection(sumo_cfg)
    conn.start()
    try:
        importer = SumoNetworkImporter(conn)
        graph = importer.import_graph()
        edges = [e for e in conn.get_edge_ids() if not e.startswith(":")]

        import random
        rng = random.Random(seed)
        requests = []
        edge_list = list(edges)
        for idx in range(num_requests):
            src_edge = rng.choice(edge_list)
            dst_edge = rng.choice(edge_list)
            src_node = conn.get_edge_from_junction(src_edge)
            dst_node = conn.get_edge_to_junction(dst_edge)
            if src_node == dst_node:
                continue
            requests.append(RoutingRequest(
                source_node=str(src_node),
                destination_node=str(dst_node),
                vehicle_id=VehicleId(f"bench_{idx}"),
                vehicle_constraints={},
                battery_state={},
                max_candidates=1,
                timeout_s=timeout_s,
            ))

        print(f"    Running {len(requests)} routing requests per algorithm...", flush=True)
        for algo_name in algo_names:
            algo = RoutingFactory.create_algorithm(algo_name)
            times: list[float] = []
            distances: list[float] = []
            successes = 0
            failures = 0
            for req in requests:
                t0 = time.perf_counter()
                r = algo.compute_route(req, graph=graph)
                elapsed = time.perf_counter() - t0
                times.append(elapsed)
                if r.success and r.primary_route:
                    successes += 1
                    distances.append(r.primary_route.total_distance_m)
                else:
                    failures += 1
            total_req = len(requests)
            results[algo_name] = {
                "success_rate": successes / total_req if total_req else 0,
                "avg_runtime_s": sum(times) / len(times) if times else 0,
                "max_runtime_s": max(times) if times else 0,
                "min_runtime_s": min(times) if times else 0,
                "avg_distance_m": sum(distances) / len(distances) if distances else 0,
                "successes": successes,
                "failures": failures,
                "total_requests": total_req,
            }
            print(f"      {algo_name:>10}: {successes}/{total_req} success, "
                  f"avg {results[algo_name]['avg_runtime_s']*1000:.1f}ms", flush=True)
    finally:
        conn.stop()
    return results


def run_experiment(config: ExperimentConfig) -> Path | None:
    _imports()
    print()
    print("=" * 72)
    print("  [3/5] FULL EXPERIMENT — ONLINE SIMULATION")
    print("=" * 72)
    print(f"  Steps={config.steps}  Vehicles={config.vehicles}  Seed={config.seed}")
    print(f"  Algorithms: {', '.join(config.algorithms)}")
    print()

    for fp, lbl in [(NET_FILE, "Network"), (NET_FILE.parent, "maps dir")]:
        if not fp.exists():
            print(f"  [ERROR] {lbl} not found: {fp}")
            return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_ROOT / f"run_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=False)
    plot_dir = output_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    print(f"  Output: {output_dir}")
    print()
    print("  Generated artifacts after completion:")
    print(f"    metrics_summary.csv     — Per-algorithm metrics table")
    print(f"    simulation_log.csv      — Per-step simulation log")
    print(f"    emergency_log.csv       — Emergency event timeline")
    print(f"    algorithm_timing.csv    — Algorithm execution timing")
    print(f"    routing_log.csv         — Offline routing benchmarks")
    print(f"    config_snapshot.yaml    — Full experiment configuration")
    print(f"    experiment_manifest.json— Machine-readable experiment record")
    print(f"    git_commit.txt          — Pinned repository commit")
    print(f"    environment.json        — Python/SUMO/OS environment")
    print(f"    network_metadata.json   — Network graph properties")
    print(f"    plots/png/              — 34 publication-ready figures")
    print(f"    plots/data/             — Plot source data CSVs")
    print()

    # Environment + git
    env = collect_environment()
    env["experiment_config"] = asdict(config)
    (output_dir / "environment.json").write_text(
        json.dumps(env, indent=2, default=str), encoding="utf-8"
    )
    (output_dir / "git_commit.txt").write_text(get_git_commit(), encoding="utf-8")

    # Config snapshot
    if yaml:
        cfg_snapshot = {
            "experiment_name": "E3-Hybrid Full Thesis Experiment",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project_version": "0.1.0",
            "sumo_version": env.get("sumo_version", "unknown"),
            "python_version": sys.version.split()[0],
            "network_file": str(NET_FILE),
            "route_file": str(ROUTE_FILE),
            "algorithms": list(config.algorithms),
            "simulation": {
                "steps": config.steps,
                "vehicles": config.vehicles,
                "departure_period_s": config.departure_period,
                "seed": config.seed,
                "reroute_interval_steps": config.reroute_interval,
                "emergency_count": config.emergency_count,
            },
            "benchmarks": {
                "offline_requests": 50,
                "timeout_s": 30.0,
                "seed": config.seed + 1,
            },
            "reproducibility": {
                "python_seed": config.seed,
                "sumo_seed": config.seed,
                "benchmark_seed": config.seed + 1,
                "emergency_seed": config.seed + 2000,
                "git_commit": get_git_commit(),
            },
        }
        (output_dir / "config_snapshot.yaml").write_text(
            yaml.dump(cfg_snapshot, default_flow_style=False), encoding="utf-8"
        )

    # Experiment manifest (machine-readable)
    manifest = {
        "git_commit": get_git_commit(),
        "git_tag": _get_git_tag(),
        "sumo_version": env.get("sumo_version", "unknown"),
        "python_version": sys.version.split()[0],
        "network": str(NET_FILE.name),
        "vehicle_count": config.vehicles,
        "simulation_steps": config.steps,
        "algorithms": list(config.algorithms),
        "seed": config.seed,
        "date": datetime.now(timezone.utc).isoformat(),
        "machine": platform.node() or os.environ.get("COMPUTERNAME", "unknown"),
        "output_directory": str(output_dir),
    }
    (output_dir / "experiment_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"  [MANIFEST] {output_dir / 'experiment_manifest.json'}")

    # Simulate each algorithm
    t_exp_start = time.time()
    sim_results: list[AlgorithmResult] = []

    for i, algo in enumerate(config.algorithms):
        print(f"  {'=' * 58}")
        print(f"  [{i+1}/{len(config.algorithms)}] {algo.upper()}")
        print(f"  {'=' * 58}")
        result = simulate_algorithm(algo, config, output_dir, i + 1, len(config.algorithms), t_exp_start)
        sim_results.append(result)
        print(f"  {'─' * 58}")
        print(f"  [{i+1}/{len(config.algorithms)}] {algo.upper()} DONE  "
              f"exec={selfmt(result.total_execution_s)}  "
              f"reroutes={result.total_reroutes}  "
              f"mem={result.peak_memory_mb:.1f}MB")
        print()

    # Write result CSVs
    write_step_csv({r.algo: r.step_log for r in sim_results}, output_dir / "simulation_log.csv")
    write_metrics_csv(sim_results, output_dir / "metrics_summary.csv")

    # Timing log
    timing_path = output_dir / "algorithm_timing.csv"
    with timing_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["algorithm", "step", "avg_reroute_latency_ms", "active_vehicles",
                     "completed_trips", "travel_time_s"])
        for r in sim_results:
            for s in r.step_log:
                w.writerow([r.algo, s.step, f"{s.reroute_latency_ms:.3f}",
                           s.active_vehicles, s.completed_trips, f"{s.travel_time_s:.3f}"])
    print(f"  [TIMING] {timing_path}")

    # Emergency log
    emerg_path = output_dir / "emergency_log.csv"
    with emerg_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["algorithm", "step", "emergency_events", "blocked_edges",
                     "congestion_edges", "active_vehicles"])
        for r in sim_results:
            for s in r.step_log:
                if s.emergency_events > 0:
                    w.writerow([r.algo, s.step, s.emergency_events,
                               s.blocked_edges, s.congestion_edges, s.active_vehicles])
    if emerg_path.stat().st_size > 0:
        print(f"  [EMERG] {emerg_path}")
    else:
        emerg_path.unlink(missing_ok=True)

    # Offline benchmarks
    print()
    print(f"  {'=' * 58}")
    print("  OFFLINE ROUTING BENCHMARKS")
    print(f"  {'=' * 58}")
    routing_results = run_offline_benchmarks(
        config.algorithms, 50, config.seed + 1, 30.0, output_dir,
    )
    routing_path = output_dir / "routing_log.csv"
    with routing_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["algorithm", "success_rate", "avg_runtime_s", "max_runtime_s",
                     "min_runtime_s", "avg_distance_m", "successes", "failures",
                     "total_requests"])
        for algo_name, stats in routing_results.items():
            w.writerow([algo_name,
                       f"{stats['success_rate']:.3f}",
                       f"{stats['avg_runtime_s']:.6f}",
                       f"{stats['max_runtime_s']:.6f}",
                       f"{stats['min_runtime_s']:.6f}",
                       f"{stats['avg_distance_m']:.1f}",
                       stats['successes'],
                       stats['failures'],
                       stats['total_requests']])

    # Network metadata
    last_algo = config.algorithms[-1]
    last_route = output_dir / f"{last_algo}.rou.xml"
    if last_route.exists():
        sumo_cfg_last = SumoConfig(
            sumo_net_file=NET_FILE, sumo_route_file=last_route,
            sumo_seed=config.seed, use_gui=False,
        )
        conn = SumoTraciConnection(sumo_cfg_last)
        conn.start()
        write_network_metadata(conn, output_dir / "network_metadata.json")
        conn.stop()

    return output_dir


# ===================================================================
#  SECTION 4 – Plot generation
# ===================================================================
def run_plot_generation() -> int:
    print()
    print("=" * 72)
    print("  [4/5] PLOT GENERATION (34 figure groups)")
    print("=" * 72)

    result = subprocess.run(
        [sys.executable, str(_PROJECT_ROOT / "scripts" / "generate_all_plots.py")],
        capture_output=True, text=True,
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if result.returncode != 0:
        print("  [WARN] Plot generation had issues.")
        return 1
    return 0


# ===================================================================
#  SECTION 5 – Final summary
# ===================================================================
def _get_git_tag_repr() -> str:
    try:
        r = subprocess.run(["git", "describe", "--tags", "--exact-match"],
                           capture_output=True, text=True, cwd=_PROJECT_ROOT)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return "unversioned"


def _categorize_artifacts(output_dir: Path) -> list[str]:
    artifacts = []
    patterns = [
        ("metrics_summary.csv", "Per-algorithm metrics table"),
        ("simulation_log.csv", "Per-step simulation log"),
        ("emergency_log.csv", "Emergency event timeline"),
        ("algorithm_timing.csv", "Algorithm execution timing"),
        ("routing_log.csv", "Offline routing benchmarks"),
        ("config_snapshot.yaml", "Experiment configuration"),
        ("experiment_manifest.json", "Machine-readable experiment record"),
        ("git_commit.txt", "Pinned repository commit"),
        ("environment.json", "Python/SUMO/OS environment"),
        ("network_metadata.json", "Network graph properties"),
    ]
    for name, desc in patterns:
        if (output_dir / name).exists():
            artifacts.append(f"  {name:<34} {desc}")
    png_dir = output_dir / "plots" / "png"
    if png_dir.is_dir():
        count = len(list(png_dir.glob("*.*")))
        artifacts.append(f"  plots/png/             {count} publication-ready figures")
    data_dir = output_dir / "plots" / "data"
    if data_dir.is_dir():
        count = len(list(data_dir.glob("*.*")))
        artifacts.append(f"  plots/data/            {count} plot data CSVs")
    return artifacts


def print_final_summary(output_dir: Path, sim_results: list, t_total: float) -> None:
    print()
    print("=" * 72)
    print("  [5/5] FINAL SUMMARY")
    print("=" * 72)
    print()

    # Find the latest experiment run
    if not output_dir or not output_dir.exists():
        runs = sorted(OUTPUT_ROOT.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        output_dir = runs[0] if runs else None

    if not output_dir:
        print("  No experiment output found.")
        return

    # -- Experiment overview --
    git_commit = get_git_commit()
    git_tag = _get_git_tag_repr()
    success = len(sim_results) > 0
    status_line = "COMPLETED SUCCESSFULLY" if success else "INCOMPLETE"

    print(f"  {status_line}")
    print()

    # Read config from snapshot
    cfg_yaml = output_dir / "config_snapshot.yaml"
    snap = None
    if cfg_yaml.exists() and yaml:
        try:
            snap = yaml.safe_load(cfg_yaml.read_text(encoding="utf-8"))
        except Exception:
            pass

    sim = snap.get("simulation", {}) if snap else {}
    algos_executed = snap.get("algorithms", []) if snap else []
    total_emergencies = sum(r.emergency_events for r in sim_results)
    total_teleports = sum(r.teleport_count for r in sim_results)
    total_vehicles = sim_results[0].total_vehicles if sim_results else sim.get("vehicles", "?")
    total_steps = sim_results[0].total_steps if sim_results else sim.get("steps", "?")

    print("  " + "─" * 58)
    print("  EXPERIMENT OVERVIEW")
    print("  " + "─" * 58)
    print(f"  Algorithms executed:     {', '.join(algos_executed) if algos_executed else 'unknown'}")
    print(f"  Total vehicles:          {total_vehicles}")
    print(f"  Simulation steps:        {total_steps}")
    print(f"  Total emergency events:  {total_emergencies}")
    print(f"  Total teleports:         {total_teleports}")
    print(f"  Total wall-clock time:   {selfmt(t_total)}")
    print(f"  Repository commit:       {git_commit[:12]}{'...' if len(git_commit) > 12 else ''}")
    print(f"  Repository tag:          {git_tag}")
    print()

    # Read metrics CSV
    metrics_csv = output_dir / "metrics_summary.csv"
    if metrics_csv.exists():
        print("  " + "─" * 58)
        print(f"  {'Algorithm':<12} {'Travel(s)':<10} {'Speed':<8} {'Reroutes':<9} "
              f"{'Thruput':<8} {'Emerg':<6} {'Telport':<8} {'Exec(s)':<9} {'Mem(MB)':<8}")
        print("  " + "─" * 58)
        with metrics_csv.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                print(f"  {row['algorithm']:<12} {row['avg_travel_time_s']:<10} "
                      f"{row['avg_speed_mps']:<8} {row['total_reroutes']:<9} "
                      f"{row['throughput']:<8} {row['emergency_events']:<6} "
                      f"{row['teleport_count']:<8} {row['total_execution_s']:<9} "
                      f"{row['peak_memory_mb']:<8}")
        print()

    # Read routing benchmarks
    routing_csv = output_dir / "routing_log.csv"
    if routing_csv.exists():
        print("  " + "─" * 58)
        print("  ROUTING BENCHMARKS")
        print("  " + "─" * 58)
        print(f"  {'Algorithm':<12} {'Success%':<9} {'Avg(ms)':<10} "
              f"{'Min(ms)':<10} {'Max(ms)':<10} {'Dist(m)':<10}")
        print("  " + "─" * 58)
        with routing_csv.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                avg_ms = float(row['avg_runtime_s']) * 1000
                min_ms = float(row['min_runtime_s']) * 1000
                max_ms = float(row['max_runtime_s']) * 1000
                print(f"  {row['algorithm']:<12} {float(row['success_rate'])*100:<9.1f} "
                      f"{avg_ms:<10.2f} {min_ms:<10.2f} {max_ms:<10.2f} "
                      f"{row['avg_distance_m']:<10}")
        print()

    # Generated artifacts
    artifacts = _categorize_artifacts(output_dir)
    if artifacts:
        print("  " + "─" * 58)
        print("  GENERATED ARTIFACTS")
        print("  " + "─" * 58)
        for a in artifacts:
            print(a)
        print()

    # Output directory
    print("  " + "─" * 58)
    print("  OUTPUT DIRECTORY")
    print("  " + "─" * 58)
    print(f"  {output_dir}")
    print()

    print(f"  Total wall-clock: {selfmt(t_total)}")
    print()

    print("  " + "=" * 58)
    print("   READY FOR THESIS DATA COLLECTION")
    print("  " + "=" * 58)
    print()
    print("  To rerun on another machine:")
    print(f"    git clone <repo-url>")
    print(f"    cd e3hybrid")
    print(f"    python preflight.py")
    print(f"    python run_thesis.py")
    print()


# ===================================================================
#  MAIN
# ===================================================================
def main() -> int:
    t_overall = time.time()

    # Step 1: Preflight
    if run_preflight() != 0:
        return 1

    # Step 2: Validation
    run_validation()

    # Step 3: Full experiment
    _imports()

    config = ExperimentConfig(
        steps=300,
        vehicles=300,
        departure_period=1.0,
        seed=42,
        algorithms=ALL_ALGORITHMS,
        reroute_interval=10,
        emergency_count=3,
    )

    output_dir = run_experiment(config)

    if not output_dir:
        return 1

    # Step 4: Plot generation
    run_plot_generation()

    # Step 5: Final summary
    t_total = time.time() - t_overall

    # Read results back for summary
    sim_results = []
    metrics_csv = output_dir / "metrics_summary.csv"
    if metrics_csv.exists():
        _imports()
        with metrics_csv.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                r = AlgorithmResult()
                r.algo = row["algorithm"]
                r.total_steps = int(row["total_steps"])
                r.total_vehicles = int(row["total_vehicles"])
                r.total_reroutes = int(row["total_reroutes"])
                r.emergency_events = int(row["emergency_events"])
                r.max_congestion_edges = int(row["max_congestion_edges"])
                r.max_blocked_edges = int(row["max_blocked_edges"])
                r.avg_travel_time_s = float(row["avg_travel_time_s"])
                r.avg_speed_mps = float(row["avg_speed_mps"])
                r.throughput = int(row["throughput"])
                r.completed_trips = int(row["completed_trips"])
                r.failed_trips = int(row["failed_trips"])
                r.teleport_count = int(row["teleport_count"])
                r.avg_rerouting_latency_ms = float(row["avg_rerouting_latency_ms"])
                r.total_execution_s = float(row["total_execution_s"])
                r.peak_memory_mb = float(row["peak_memory_mb"])
                sim_results.append(r)

    print_final_summary(output_dir, sim_results, t_total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
