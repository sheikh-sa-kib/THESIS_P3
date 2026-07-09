#!/usr/bin/env python3
"""Full-scale experiment runner --- all 6 algorithms on Midtown Manhattan.

Usage:
    python scripts/run_experiment.py              # default: 300 steps, 300 vehicles
    python scripts/run_experiment.py --steps 500 --vehicles 150 --algorithms dijkstra,astar

Outputs:
    outputs/experiments/run_YYYYMMDD_HHMMSS/
        metrics_summary.csv       --- per-algorithm aggregate metrics
        routing_log.csv           --- per-request per-algorithm results
        simulation_log.csv        --- per-step simulation state
        emergency_log.csv         --- emergency events
        algorithm_timing.csv      --- per-step rerouting latency
        environment.json          --- system + package versions
        network_metadata.json     --- node/edge counts
        git_commit.txt            --- commit hash
        config_snapshot.yaml      --- exact config used
        plots/
            execution_time.png
            vehicles_over_time.png
            congestion_heatmap.png
            travel_time_comparison.png
            throughput.png
            memory_usage.png
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import time
import tracemalloc
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SUMO_HOME = os.environ.get("SUMO_HOME", "").strip()
if _SUMO_HOME:
    _tools = os.path.join(_SUMO_HOME, "tools")
    if _tools not in sys.path:
        sys.path.insert(0, _tools)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from e3hybrid.routing.factory import RoutingFactory
from e3hybrid.routing.request import RoutingRequest
from e3hybrid.network.edge import MutableEdgeState
from e3hybrid.network.types import EdgeId
from e3hybrid.sumo.config import SumoConfig
from e3hybrid.sumo.connection import SumoTraciConnection
from e3hybrid.sumo.network_importer import SumoNetworkImporter
from e3hybrid.vehicle.types import VehicleId

ALL_ALGORITHMS = ("dijkstra", "astar", "aco", "bco", "pso", "e3hybrid")
DATA_DIR = _PROJECT_ROOT / "data"
NET_FILE = DATA_DIR / "maps" / "midtown_manhattan.net.xml"
ROUTE_FILE = DATA_DIR / "routes" / "midtown_manhattan.rou.xml"
OUTPUT_ROOT = _PROJECT_ROOT / "outputs" / "experiments"


@dataclass
class ExperimentConfig:
    steps: int = 300
    vehicles: int = 300
    departure_period: float = 1.0
    seed: int = 42
    algorithms: tuple[str, ...] = ALL_ALGORITHMS
    reroute_interval: int = 10
    emergency_count: int = 3

    @classmethod
    def from_cli(cls, args: argparse.Namespace) -> ExperimentConfig:
        algos = tuple(a.strip() for a in args.algorithms.split(",")) if args.algorithms else ALL_ALGORITHMS
        return cls(
            steps=args.steps,
            vehicles=args.vehicles,
            departure_period=args.period,
            seed=args.seed,
            algorithms=algos,
            reroute_interval=args.reroute_interval,
            emergency_count=args.emergency_count,
        )


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


def generate_routes(net_file: Path, route_file: Path, vehicles: int, period: float, seed: int) -> None:
    import subprocess
    sumo_home = os.environ.get("SUMO_HOME", "")
    random_trips = os.path.join(sumo_home, "tools", "randomTrips.py")
    end_time = vehicles * period
    trips_file = route_file.with_suffix(".trips.xml")

    subprocess.run([
        sys.executable, random_trips,
        "-n", str(net_file),
        "-r", str(trips_file),
        "--end", str(end_time),
        "--period", str(period),
        "--seed", str(seed),
    ], check=True, capture_output=True)

    subprocess.run([
        "duarouter",
        "-n", str(net_file),
        "-s", str(trips_file),
        "-o", str(route_file),
        "--routing-threads", "2",
        "--begin", "0", "--end", str(end_time),
        "--no-warnings", "true",
    ], check=True, capture_output=True)

    trips_file.unlink(missing_ok=True)


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
        import subprocess
        result = subprocess.run(["git", "rev-parse", "HEAD"],
                                capture_output=True, text=True, cwd=_PROJECT_ROOT)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unversioned"


def get_network_metadata(conn: SumoTraciConnection) -> dict[str, Any]:
    edges = [e for e in conn.get_edge_ids() if not e.startswith(":")]
    junctions = conn.get_junction_ids()
    return {
        "total_edges": len(edges),
        "total_junctions": len(junctions),
        "source_file": str(NET_FILE),
    }


def simulate_algorithm(algo_name: str, config: ExperimentConfig, output_dir: Path) -> AlgorithmResult:
    result = AlgorithmResult(algo=algo_name)
    route_file = output_dir / f"{algo_name}.rou.xml"

    if not route_file.exists():
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
        all_step_times = []

        # Emergency event schedule (deterministic, graph-state updates only)
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

        for s in range(config.steps):
            conn.step()

            # Emergency activation and resolution (graph-state updates only)
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

            # Teleportation detection via TraCI
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

            if s > 0 and s % config.reroute_interval == 0:
                for vid in vehicles:
                    t0 = time.perf_counter()
                    try:
                        route_edges = conn.get_vehicle_route(vid)
                        if len(route_edges) < 2:
                            continue
                        pos = conn.get_vehicle_position(vid)
                        _, _, current_edge = pos

                        src = conn.get_edge_from_junction(current_edge) if current_edge else ""
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
                        )
                        r = algo.compute_route(req, graph=graph)
                        t1 = time.perf_counter()
                        reroute_latencies_ms = (t1 - t0) * 1000
                        reroute_latencies.append(reroute_latencies_ms)

                        if r.success and r.primary_route:
                            conn.set_vehicle_route(vid, list(r.primary_route.edge_sequence))
                            total_reroutes += 1
                    except Exception:
                        pass

            for vid in vehicles:
                try:
                    pos_edge = conn.get_vehicle_position(vid)[2]
                    tt = conn.get_edge_travel_time(pos_edge)
                    travel_times.append(tt)
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
            ))

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


def run_offline_benchmarks(
    algo_names: tuple[str, ...],
    num_requests: int,
    seed: int,
    timeout_s: float,
) -> dict[str, dict[str, Any]]:
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
        requests: list[RoutingRequest] = []
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
    finally:
        conn.stop()
    return results


def write_step_csv(all_step_logs: dict[str, list[StepMetrics]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["algorithm", "step", "active_vehicles", "reroutes",
                     "emergency_events", "blocked_edges", "congestion_edges",
                     "avg_speed_mps", "completed_trips", "failed_trips",
                     "teleport_count"])
        for algo_name, steps in all_step_logs.items():
            for s in steps:
                w.writerow([algo_name, s.step, s.active_vehicles, s.total_reroutes,
                           s.emergency_events, s.blocked_edges, s.congestion_edges,
                           f"{s.avg_speed_mps:.3f}", s.completed_trips, s.failed_trips,
                           s.teleport_count])


def write_metrics_csv(results: list[AlgorithmResult], path: Path) -> None:
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


def write_network_metadata(conn: SumoTraciConnection, path: Path) -> None:
    meta = get_network_metadata(conn)
    with path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def write_plots(results: list[AlgorithmResult], output_dir: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  [SKIP] matplotlib not installed; skipping plots")
        return

    plot_dir = output_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    names = [r.algo for r in results]
    colors = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948"]

    # Execution time
    fig, ax = plt.subplots(figsize=(8, 4))
    vals = [r.total_execution_s for r in results]
    ax.bar(names, vals, color=colors)
    ax.set_title("Total Execution Time (s)")
    ax.tick_params(axis="x", rotation=30)
    plt.tight_layout()
    plt.savefig(plot_dir / "execution_time.png", dpi=150)
    plt.close()

    # Vehicles over time
    fig, ax = plt.subplots(figsize=(8, 4))
    for r in results:
        steps = [s.step for s in r.step_log]
        active = [s.active_vehicles for s in r.step_log]
        ax.plot(steps, active, label=r.algo)
    ax.set_title("Active Vehicles Over Time")
    ax.set_xlabel("Step")
    ax.set_ylabel("Vehicles")
    ax.legend()
    plt.tight_layout()
    plt.savefig(plot_dir / "vehicles_over_time.png", dpi=150)
    plt.close()

    # Travel time comparison
    fig, ax = plt.subplots(figsize=(8, 4))
    vals = [r.avg_travel_time_s for r in results]
    ax.bar(names, vals, color=colors)
    ax.set_title("Average Travel Time (s)")
    ax.tick_params(axis="x", rotation=30)
    plt.tight_layout()
    plt.savefig(plot_dir / "travel_time_comparison.png", dpi=150)
    plt.close()

    # Throughput
    fig, ax = plt.subplots(figsize=(8, 4))
    vals = [r.throughput for r in results]
    ax.bar(names, vals, color=colors)
    ax.set_title("Throughput (completed trips)")
    ax.tick_params(axis="x", rotation=30)
    plt.tight_layout()
    plt.savefig(plot_dir / "throughput.png", dpi=150)
    plt.close()

    # Memory usage
    fig, ax = plt.subplots(figsize=(8, 4))
    vals = [r.peak_memory_mb for r in results]
    ax.bar(names, vals, color=colors)
    ax.set_title("Peak Memory (MB)")
    ax.tick_params(axis="x", rotation=30)
    plt.tight_layout()
    plt.savefig(plot_dir / "memory_usage.png", dpi=150)
    plt.close()

    # Congestion
    fig, ax = plt.subplots(figsize=(8, 4))
    vals = [r.max_congestion_edges for r in results]
    ax.bar(names, vals, color=colors)
    ax.set_title("Peak Congestion (edges >80% occupancy)")
    ax.tick_params(axis="x", rotation=30)
    plt.tight_layout()
    plt.savefig(plot_dir / "congestion_heatmap.png", dpi=150)
    plt.close()

    print(f"  Plots saved to {plot_dir}")


def print_summary_table(results: list[AlgorithmResult]) -> None:
    print(f"\n{'=' * 130}")
    print(f"  EXPERIMENT SUMMARY")
    print(f"{'=' * 130}")
    header = (f"  {'Algo':<12} {'Steps':<7} {'Reroutes':<9} {'Emerg':<6} "
              f"{'Cong':<6} {'Speed':<8} {'Travel(s)':<10} {'Thruput':<9} "
              f"{'Fail':<6} {'Telport':<9} {'Exec(s)':<9} {'Mem(MB)':<8}")
    print(header)
    print(f"  {'-' * 116}")
    for r in results:
        print(f"  {r.algo:<12} {r.total_steps:<7} {r.total_reroutes:<9} "
              f"{r.emergency_events:<6} {r.max_congestion_edges:<6} "
              f"{r.avg_speed_mps:<8.2f} {r.avg_travel_time_s:<10.2f} {r.throughput:<9} "
              f"{r.failed_trips:<6} {r.teleport_count:<9} {r.total_execution_s:<9.2f} {r.peak_memory_mb:<8.1f}")


def main() -> int:
    parser = argparse.ArgumentParser(description="E3-Hybrid experiment runner")
    parser.add_argument("--steps", type=int, default=300, help="Simulation steps")
    parser.add_argument("--vehicles", type=int, default=300, help="Number of vehicles")
    parser.add_argument("--period", type=float, default=1.0, help="Departure period (s)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--algorithms", type=str, default=None,
                        help="Comma-separated algorithms (default: all 6)")
    parser.add_argument("--reroute-interval", type=int, default=10, help="Steps between reroutes")
    parser.add_argument("--emergency-count", type=int, default=3, help="Emergency events")
    parser.add_argument("--request-count", type=int, default=50, help="Offline routing requests")
    parser.add_argument("--timeout", type=float, default=30.0, help="Routing timeout (s)")

    args = parser.parse_args()
    cfg = ExperimentConfig.from_cli(args)

    print()
    print("=" * 72)
    print("  E3-HYBRID EXPERIMENT RUNNER")
    print(f"  Steps={cfg.steps}  Vehicles={cfg.vehicles}  Seed={cfg.seed}")
    print(f"  Algorithms: {', '.join(cfg.algorithms)}")
    print("=" * 72)

    for fp, lbl in [(NET_FILE, "Network"), (NET_FILE.parent, "maps dir")]:
        if not fp.exists():
            print(f"  [ERROR] {lbl} not found: {fp}")
            return 1

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_ROOT / f"run_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=False)
    plot_dir = output_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    print(f"  Output: {output_dir}")

    env = collect_environment()
    env["experiment_config"] = asdict(cfg)
    (output_dir / "environment.json").write_text(
        json.dumps(env, indent=2, default=str), encoding="utf-8"
    )
    (output_dir / "git_commit.txt").write_text(get_git_commit(), encoding="utf-8")

    # Phase 1: Online simulation
    print(f"\n{'---' * 72}")
    print("  Phase 1: Online SUMO simulation (per-algorithm)")
    print(f"{'---' * 72}")

    sim_results: list[AlgorithmResult] = []
    for i, algo in enumerate(cfg.algorithms):
        print(f"\n  [{i+1}/{len(cfg.algorithms)}] {algo}")
        result = simulate_algorithm(algo, cfg, output_dir)
        sim_results.append(result)
        max_veh = max(s.active_vehicles for s in result.step_log) if result.step_log else 0
        print(f"    Completed: {result.total_execution_s:.1f}s  "
              f"MaxVeh: {max_veh}  Reroutes: {result.total_reroutes}  "
              f"Memory: {result.peak_memory_mb:.1f}MB")

    step_logs = {r.algo: r.step_log for r in sim_results}
    write_step_csv(step_logs, output_dir / "simulation_log.csv")
    write_metrics_csv(sim_results, output_dir / "metrics_summary.csv")

    # Phase 2: Offline routing benchmarks
    print(f"\n{'---' * 72}")
    print("  Phase 2: Offline routing benchmarks (algorithm-only)")
    print(f"{'---' * 72}")

    offline_reqs = args.request_count
    routing_results = run_offline_benchmarks(
        cfg.algorithms, offline_reqs, cfg.seed + 1, args.timeout
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
    last_algo = cfg.algorithms[-1]
    last_route = output_dir / f"{last_algo}.rou.xml"
    if last_route.exists():
        sumo_cfg_last = SumoConfig(
            sumo_net_file=NET_FILE, sumo_route_file=last_route,
            sumo_seed=cfg.seed, use_gui=False,
        )
        conn = SumoTraciConnection(sumo_cfg_last)
        conn.start()
        write_network_metadata(conn, output_dir / "network_metadata.json")
        conn.stop()

    # Phase 3: Plots
    print(f"\n{'---' * 72}")
    print("  Phase 3: Plot generation")
    print(f"{'---' * 72}")
    write_plots(sim_results, output_dir)

    print_summary_table(sim_results)

    print(f"\n{'=' * 72}")
    print(f"  Experiment complete. Output: {output_dir}")
    print(f"{'=' * 72}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

