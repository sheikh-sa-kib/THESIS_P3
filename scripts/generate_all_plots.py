#!/usr/bin/env python3
"""Post-processing: generate all thesis figures from saved experiment CSVs.

Usage:
    python scripts/generate_all_plots.py                                    # latest run
    python scripts/generate_all_plots.py --input outputs/experiments/run_*  # specific run
    python scripts/generate_all_plots.py --output my_thesis_figures          # custom output

Output:
    <output_dir>/
        png/       (300 DPI, RGB)
        pdf/       (vector, publication-quality)
        data/      (processed datasets for reproducibility)
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

ALGO_ORDER = ("dijkstra", "astar", "aco", "bco", "pso", "e3hybrid")
ALGO_COLORS = ("#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948")
ALGO_MARKERS = ("o", "s", "D", "^", "v", "X")


@dataclass
class MetricsRow:
    algorithm: str = ""
    total_steps: int = 0
    total_vehicles: int = 0
    total_reroutes: int = 0
    emergency_events: int = 0
    max_congestion_edges: int = 0
    max_blocked_edges: int = 0
    avg_travel_time_s: float = 0.0
    avg_speed_mps: float = 0.0
    throughput: int = 0
    completed_trips: int = 0
    failed_trips: int = 0
    teleport_count: int = 0
    avg_rerouting_latency_ms: float = 0.0
    total_execution_s: float = 0.0
    peak_memory_mb: float = 0.0


@dataclass
class StepRow:
    algorithm: str = ""
    step: int = 0
    active_vehicles: int = 0
    reroutes: int = 0
    emergency_events: int = 0
    blocked_edges: int = 0
    congestion_edges: int = 0
    avg_speed_mps: float = 0.0
    completed_trips: int = 0
    failed_trips: int = 0
    teleport_count: int = 0
    travel_time_s: float = 0.0
    reroute_latency_ms: float = 0.0


@dataclass
class RoutingRow:
    algorithm: str = ""
    success_rate: float = 0.0
    avg_runtime_s: float = 0.0
    max_runtime_s: float = 0.0
    min_runtime_s: float = 0.0
    avg_distance_m: float = 0.0
    successes: int = 0
    failures: int = 0
    total_requests: int = 0


@dataclass
class ExpData:
    metrics: list[MetricsRow] = field(default_factory=list)
    steps: list[StepRow] = field(default_factory=list)
    routing: list[RoutingRow] = field(default_factory=list)
    env: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# CSV readers
# ---------------------------------------------------------------------------

def _parse_float(v: str) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def _parse_int(v: str) -> int:
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


def read_metrics_csv(path: Path) -> list[MetricsRow]:
    rows: list[MetricsRow] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            m = MetricsRow(
                algorithm=row.get("algorithm", ""),
                total_steps=_parse_int(row.get("total_steps", "0")),
                total_vehicles=_parse_int(row.get("total_vehicles", "0")),
                total_reroutes=_parse_int(row.get("total_reroutes", "0")),
                emergency_events=_parse_int(row.get("emergency_events", "0")),
                max_congestion_edges=_parse_int(row.get("max_congestion_edges", "0")),
                max_blocked_edges=_parse_int(row.get("max_blocked_edges", "0")),
                avg_travel_time_s=_parse_float(row.get("avg_travel_time_s", "0")),
                avg_speed_mps=_parse_float(row.get("avg_speed_mps", "0")),
                throughput=_parse_int(row.get("throughput", "0")),
                completed_trips=_parse_int(row.get("completed_trips", "0")),
                failed_trips=_parse_int(row.get("failed_trips", "0")),
                teleport_count=_parse_int(row.get("teleport_count", "0")),
                avg_rerouting_latency_ms=_parse_float(row.get("avg_rerouting_latency_ms", "0")),
                total_execution_s=_parse_float(row.get("total_execution_s", "0")),
                peak_memory_mb=_parse_float(row.get("peak_memory_mb", "0")),
            )
            rows.append(m)
    return rows


def read_step_csv(path: Path) -> list[StepRow]:
    rows: list[StepRow] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            s = StepRow(
                algorithm=row.get("algorithm", ""),
                step=_parse_int(row.get("step", "0")),
                active_vehicles=_parse_int(row.get("active_vehicles", "0")),
                reroutes=_parse_int(row.get("reroutes", "0")),
                emergency_events=_parse_int(row.get("emergency_events", "0")),
                blocked_edges=_parse_int(row.get("blocked_edges", "0")),
                congestion_edges=_parse_int(row.get("congestion_edges", "0")),
                avg_speed_mps=_parse_float(row.get("avg_speed_mps", "0")),
                completed_trips=_parse_int(row.get("completed_trips", "0")),
                failed_trips=_parse_int(row.get("failed_trips", "0")),
                teleport_count=_parse_int(row.get("teleport_count", "0")),
                travel_time_s=_parse_float(row.get("travel_time_s", "0")),
                reroute_latency_ms=_parse_float(row.get("reroute_latency_ms", "0")),
            )
            rows.append(s)
    return rows


def read_routing_csv(path: Path) -> list[RoutingRow]:
    rows: list[RoutingRow] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            r = RoutingRow(
                algorithm=row.get("algorithm", ""),
                success_rate=_parse_float(row.get("success_rate", "0")),
                avg_runtime_s=_parse_float(row.get("avg_runtime_s", "0")),
                max_runtime_s=_parse_float(row.get("max_runtime_s", "0")),
                min_runtime_s=_parse_float(row.get("min_runtime_s", "0")),
                avg_distance_m=_parse_float(row.get("avg_distance_m", "0")),
                successes=_parse_int(row.get("successes", "0")),
                failures=_parse_int(row.get("failures", "0")),
                total_requests=_parse_int(row.get("total_requests", "0")),
            )
            rows.append(r)
    return rows


def load_experiment(run_dir: Path) -> ExpData:
    data = ExpData()
    data.metrics = read_metrics_csv(run_dir / "metrics_summary.csv")
    data.steps = read_step_csv(run_dir / "simulation_log.csv")
    data.routing = read_routing_csv(run_dir / "routing_log.csv")
    env_path = run_dir / "environment.json"
    if env_path.exists():
        data.env = json.loads(env_path.read_text(encoding="utf-8"))
    return data


def _algo_sort_key(algo: str) -> int:
    try:
        return ALGO_ORDER.index(algo.lower())
    except ValueError:
        return 999


def _sorted_metrics(data: ExpData) -> list[MetricsRow]:
    return sorted(data.metrics, key=lambda m: _algo_sort_key(m.algorithm))


def _sorted_steps(data: ExpData) -> list[StepRow]:
    return sorted(data.steps, key=lambda s: (_algo_sort_key(s.algorithm), s.step))


def _sorted_routing(data: ExpData) -> list[RoutingRow]:
    return sorted(data.routing, key=lambda r: _algo_sort_key(r.algorithm))


def _group_steps(data: ExpData) -> dict[str, list[StepRow]]:
    groups: dict[str, list[StepRow]] = defaultdict(list)
    for s in _sorted_steps(data):
        groups[s.algorithm].append(s)
    return dict(groups)


def _names_and_vals(metrics: list[MetricsRow], attr: str) -> tuple[list[str], list[float]]:
    names = [m.algorithm for m in metrics]
    vals = [getattr(m, attr, 0) for m in metrics]
    return names, vals


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

_INITIALIZED_MATPLOTLIB = False
plt = None  # set by _init_plt


def _init_plt():
    global _INITIALIZED_MATPLOTLIB, plt
    if _INITIALIZED_MATPLOTLIB:
        return
    _INITIALIZED_MATPLOTLIB = True
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as _plt
    plt = _plt
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 12,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def _save_fig(fig, stem: str, out_dir: Path):
    global plt
    png_dir = out_dir / "png"
    pdf_dir = out_dir / "pdf"
    svg_dir = out_dir / "svg"
    png_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    svg_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_dir / f"{stem}.png", dpi=300)
    fig.savefig(pdf_dir / f"{stem}.pdf", dpi=300)
    fig.savefig(svg_dir / f"{stem}.svg", dpi=300)
    plt.close(fig)


def _bar(ax, names, vals, colors=ALGO_COLORS, ylabel="", title="",
         rotate_x=True, yerr=None):
    x = range(len(names))
    bars = ax.bar(x, vals, color=colors[:len(names)], width=0.65, yerr=yerr,
                  capsize=4, edgecolor="black", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30 if rotate_x else 0, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.3)
    for bar, v in zip(bars, vals):
        if v != 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    f"{v:.1f}", ha="center", va="bottom", fontsize=7)
    return bars


def _line(ax, x_vals, y_dict, xlabel="", ylabel="", title=""):
    for i, (label, y) in enumerate(y_dict.items()):
        ax.plot(x_vals, y, label=label, color=ALGO_COLORS[i % len(ALGO_COLORS)],
                marker=ALGO_MARKERS[i % len(ALGO_MARKERS)], markersize=3, linewidth=1.2)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(frameon=True, fancybox=True, shadow=True)
    ax.grid(alpha=0.3)


# ---------------------------------------------------------------------------
# Figure generators — each saves its own PNG + PDF
# ---------------------------------------------------------------------------


def fig_bar_travel_time(data: ExpData, out_dir: Path):
    names, vals = _names_and_vals(_sorted_metrics(data), "avg_travel_time_s")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _bar(ax, names, vals, ylabel="Average Travel Time (s)", title="Average Travel Time per Route")
    _save_fig(fig, "bar_avg_travel_time", out_dir)


def fig_bar_execution_time(data: ExpData, out_dir: Path):
    names, vals = _names_and_vals(_sorted_metrics(data), "total_execution_s")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _bar(ax, names, vals, ylabel="Total Execution Time (s)", title="Algorithm Execution Time")
    _save_fig(fig, "bar_execution_time", out_dir)


def fig_bar_memory(data: ExpData, out_dir: Path):
    names, vals = _names_and_vals(_sorted_metrics(data), "peak_memory_mb")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _bar(ax, names, vals, ylabel="Peak Memory (MB)", title="Peak Memory Usage")
    _save_fig(fig, "bar_memory_usage", out_dir)


def fig_bar_reroutes(data: ExpData, out_dir: Path):
    names, vals = _names_and_vals(_sorted_metrics(data), "total_reroutes")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _bar(ax, names, vals, ylabel="Total Reroutes", title="Total Rerouting Operations")
    _save_fig(fig, "bar_reroutes", out_dir)


def fig_bar_throughput(data: ExpData, out_dir: Path):
    names, vals = _names_and_vals(_sorted_metrics(data), "throughput")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _bar(ax, names, vals, ylabel="Completed Trips", title="Throughput (Completed Trips)")
    _save_fig(fig, "bar_throughput", out_dir)


def fig_bar_teleports(data: ExpData, out_dir: Path):
    names, vals = _names_and_vals(_sorted_metrics(data), "teleport_count")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _bar(ax, names, vals, ylabel="Teleported Vehicles", title="Teleport Count")
    _save_fig(fig, "bar_teleports", out_dir)


def fig_bar_emergency(data: ExpData, out_dir: Path):
    names, vals = _names_and_vals(_sorted_metrics(data), "emergency_events")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _bar(ax, names, vals, ylabel="Emergency Events", title="Emergency Events Handled")
    _save_fig(fig, "bar_emergency_events", out_dir)


def fig_bar_congestion(data: ExpData, out_dir: Path):
    names, vals = _names_and_vals(_sorted_metrics(data), "max_congestion_edges")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _bar(ax, names, vals, ylabel="Congested Edges (peak)", title="Peak Congestion (>80% Occupancy)")
    _save_fig(fig, "bar_congestion", out_dir)


def fig_bar_speed(data: ExpData, out_dir: Path):
    names, vals = _names_and_vals(_sorted_metrics(data), "avg_speed_mps")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _bar(ax, names, vals, ylabel="Average Speed (m/s)", title="Average Traffic Speed")
    _save_fig(fig, "bar_avg_speed", out_dir)


def fig_bar_reroute_latency(data: ExpData, out_dir: Path):
    names, vals = _names_and_vals(_sorted_metrics(data), "avg_rerouting_latency_ms")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _bar(ax, names, vals, ylabel="Avg Reroute Latency (ms)", title="Average Rerouting Latency")
    _save_fig(fig, "bar_reroute_latency", out_dir)


def fig_bar_blocked(data: ExpData, out_dir: Path):
    names, vals = _names_and_vals(_sorted_metrics(data), "max_blocked_edges")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _bar(ax, names, vals, ylabel="Blocked Edges (peak)", title="Peak Blocked Edges (>95% Occupancy)")
    _save_fig(fig, "bar_blocked_edges", out_dir)


def fig_bar_failed_trips(data: ExpData, out_dir: Path):
    names, vals = _names_and_vals(_sorted_metrics(data), "failed_trips")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _bar(ax, names, vals, ylabel="Failed Trips", title="Failed Trip Count")
    _save_fig(fig, "bar_failed_trips", out_dir)


def fig_bar_routing_success(data: ExpData, out_dir: Path):
    names = [r.algorithm for r in _sorted_routing(data)]
    succ = [r.successes for r in _sorted_routing(data)]
    fail = [r.failures for r in _sorted_routing(data)]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = range(len(names))
    ax.bar(x, succ, width=0.6, label="Success", color="#2ecc71", edgecolor="black", linewidth=0.5)
    ax.bar(x, fail, width=0.6, bottom=succ, label="Failure", color="#e74c3c", edgecolor="black", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30, ha="right")
    ax.set_ylabel("Routing Requests")
    ax.set_title("Offline Routing Success / Failure")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    _save_fig(fig, "bar_routing_success_failure", out_dir)


def fig_bar_runtime_with_range(data: ExpData, out_dir: Path):
    names = [r.algorithm for r in _sorted_routing(data)]
    avg_v = [r.avg_runtime_s for r in _sorted_routing(data)]
    min_v = [r.min_runtime_s for r in _sorted_routing(data)]
    max_v = [r.max_runtime_s for r in _sorted_routing(data)]
    yerr_low = [avg_v[i] - min_v[i] for i in range(len(names))]
    yerr_high = [max_v[i] - avg_v[i] for i in range(len(names))]
    yerr = [yerr_low, yerr_high]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _bar(ax, names, avg_v, ylabel="Runtime (s)", title="Offline Routing Runtime (min/avg/max)", yerr=yerr)
    _save_fig(fig, "bar_routing_runtime", out_dir)


def fig_bar_routing_distance(data: ExpData, out_dir: Path):
    names = [r.algorithm for r in _sorted_routing(data)]
    dists = [r.avg_distance_m for r in _sorted_routing(data)]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _bar(ax, names, dists, ylabel="Average Distance (m)", title="Average Route Distance (Offline)")
    _save_fig(fig, "bar_routing_distance", out_dir)


def fig_bar_routing_success_rate(data: ExpData, out_dir: Path):
    names = [r.algorithm for r in _sorted_routing(data)]
    rates = [r.success_rate * 100 for r in _sorted_routing(data)]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _bar(ax, names, rates, ylabel="Success Rate (%)", title="Offline Routing Success Rate")
    ax.set_ylim(0, 105)
    _save_fig(fig, "bar_routing_success_rate", out_dir)


# ---- Time series ----

def fig_line_active_vehicles(data: ExpData, out_dir: Path):
    groups = _group_steps(data)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    y_dict = {}
    for algo in ALGO_ORDER:
        grp = groups.get(algo, [])
        if grp:
            y_dict[algo] = [s.active_vehicles for s in grp]
    if not y_dict:
        plt.close(fig)
        return
    steps = list(range(len(next(iter(y_dict.values())))))
    _line(ax, steps, y_dict, xlabel="Simulation Step", ylabel="Active Vehicles",
          title="Active Vehicles Over Time")
    _save_fig(fig, "line_active_vehicles", out_dir)


def fig_line_congestion(data: ExpData, out_dir: Path):
    groups = _group_steps(data)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    y_dict = {}
    for algo in ALGO_ORDER:
        grp = groups.get(algo, [])
        if grp:
            y_dict[algo] = [s.congestion_edges for s in grp]
    if not y_dict:
        plt.close(fig)
        return
    steps = list(range(len(next(iter(y_dict.values())))))
    _line(ax, steps, y_dict, xlabel="Simulation Step", ylabel="Congested Edges",
          title="Congestion Over Time")
    _save_fig(fig, "line_congestion", out_dir)


def fig_line_completed(data: ExpData, out_dir: Path):
    groups = _group_steps(data)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    y_dict = {}
    for algo in ALGO_ORDER:
        grp = groups.get(algo, [])
        if grp:
            y_dict[algo] = [s.completed_trips for s in grp]
    if not y_dict:
        plt.close(fig)
        return
    steps = list(range(len(next(iter(y_dict.values())))))
    _line(ax, steps, y_dict, xlabel="Simulation Step", ylabel="Completed Trips",
          title="Cumulative Completed Trips Over Time")
    _save_fig(fig, "line_completed_trips", out_dir)


def fig_line_teleports(data: ExpData, out_dir: Path):
    groups = _group_steps(data)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    y_dict = {}
    for algo in ALGO_ORDER:
        grp = groups.get(algo, [])
        if grp:
            y_dict[algo] = [s.teleport_count for s in grp]
    if not y_dict:
        plt.close(fig)
        return
    steps = list(range(len(next(iter(y_dict.values())))))
    _line(ax, steps, y_dict, xlabel="Simulation Step", ylabel="Teleported Vehicles",
          title="Teleport Count Over Time")
    _save_fig(fig, "line_teleports", out_dir)


def fig_line_speed(data: ExpData, out_dir: Path):
    groups = _group_steps(data)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    y_dict = {}
    for algo in ALGO_ORDER:
        grp = groups.get(algo, [])
        if grp:
            y_dict[algo] = [s.avg_speed_mps for s in grp]
    if not y_dict:
        plt.close(fig)
        return
    steps = list(range(len(next(iter(y_dict.values())))))
    _line(ax, steps, y_dict, xlabel="Simulation Step", ylabel="Average Speed (m/s)",
          title="Average Traffic Speed Over Time")
    _save_fig(fig, "line_avg_speed", out_dir)


def fig_line_travel_time(data: ExpData, out_dir: Path):
    groups = _group_steps(data)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    y_dict = {}
    for algo in ALGO_ORDER:
        grp = groups.get(algo, [])
        if grp:
            tt = [s.travel_time_s for s in grp]
            if any(v > 0 for v in tt):
                y_dict[algo] = tt
    if not y_dict:
        plt.close(fig)
        return
    steps = list(range(len(next(iter(y_dict.values())))))
    _line(ax, steps, y_dict, xlabel="Simulation Step", ylabel="Travel Time (s)",
          title="Average Travel Time Over Time")
    _save_fig(fig, "line_travel_time", out_dir)


def fig_line_reroute_latency(data: ExpData, out_dir: Path):
    groups = _group_steps(data)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    y_dict = {}
    for algo in ALGO_ORDER:
        grp = groups.get(algo, [])
        if grp:
            lat = [s.reroute_latency_ms for s in grp]
            if any(v > 0 for v in lat):
                y_dict[algo] = lat
    if not y_dict:
        plt.close(fig)
        return
    steps = list(range(len(next(iter(y_dict.values())))))
    _line(ax, steps, y_dict, xlabel="Simulation Step", ylabel="Reroute Latency (ms)",
          title="Rerouting Latency Over Time")
    _save_fig(fig, "line_reroute_latency", out_dir)


def fig_line_blocked(data: ExpData, out_dir: Path):
    groups = _group_steps(data)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    y_dict = {}
    for algo in ALGO_ORDER:
        grp = groups.get(algo, [])
        if grp:
            blk = [s.blocked_edges for s in grp]
            if any(v > 0 for v in blk):
                y_dict[algo] = blk
    if not y_dict:
        plt.close(fig)
        return
    steps = list(range(len(next(iter(y_dict.values())))))
    _line(ax, steps, y_dict, xlabel="Simulation Step", ylabel="Blocked Edges",
          title="Blocked Edges Over Time (>95% Occupancy)")
    _save_fig(fig, "line_blocked_edges", out_dir)


# ---- Distributions ----

def fig_boxplot_travel_time(data: ExpData, out_dir: Path):
    groups = _group_steps(data)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    datasets = []
    labels = []
    for algo in ALGO_ORDER:
        grp = groups.get(algo, [])
        if grp:
            tt = [s.travel_time_s for s in grp if s.travel_time_s > 0]
            if tt:
                datasets.append(tt)
                labels.append(algo)
    if not datasets:
        plt.close(fig)
        return
    bp = ax.boxplot(datasets, patch_artist=True, showmeans=True,
                    meanprops=dict(marker="D", markerfacecolor="white", markeredgecolor="black"))
    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    for patch, color in zip(bp["boxes"], ALGO_COLORS[:len(datasets)]):
        patch.set_facecolor(color)
    ax.set_ylabel("Travel Time (s)")
    ax.set_title("Travel Time Distribution Across Algorithms")
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", alpha=0.3)
    _save_fig(fig, "boxplot_travel_time", out_dir)


def fig_violin_travel_time(data: ExpData, out_dir: Path):
    groups = _group_steps(data)
    fig, ax = plt.subplots(figsize=(8, 5))
    datasets = []
    labels = []
    for algo in ALGO_ORDER:
        grp = groups.get(algo, [])
        if grp:
            tt = [s.travel_time_s for s in grp if s.travel_time_s > 0]
            if tt:
                datasets.append(tt)
                labels.append(algo)
    if not datasets:
        plt.close(fig)
        return
    parts = ax.violinplot(datasets, showmeans=True, showmedians=True)
    for i, pc in enumerate(parts["bodies"]):
        pc.set_facecolor(ALGO_COLORS[i % len(ALGO_COLORS)])
        pc.set_alpha(0.7)
    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylabel("Travel Time (s)")
    ax.set_title("Travel Time Distribution (Violin Plot)")
    ax.grid(axis="y", alpha=0.3)
    _save_fig(fig, "violin_travel_time", out_dir)


def fig_histogram_speed(data: ExpData, out_dir: Path):
    groups = _group_steps(data)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for i, algo in enumerate(ALGO_ORDER):
        grp = groups.get(algo, [])
        if grp:
            speeds = [s.avg_speed_mps for s in grp if s.avg_speed_mps > 0]
            if speeds:
                ax.hist(speeds, bins=20, alpha=0.5, label=algo, color=ALGO_COLORS[i])
    ax.set_xlabel("Average Speed (m/s)")
    ax.set_ylabel("Frequency")
    ax.set_title("Distribution of Average Traffic Speeds")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    _save_fig(fig, "hist_speed", out_dir)


def fig_histogram_travel_time(data: ExpData, out_dir: Path):
    groups = _group_steps(data)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for i, algo in enumerate(ALGO_ORDER):
        grp = groups.get(algo, [])
        if grp:
            tt = [s.travel_time_s for s in grp if s.travel_time_s > 0]
            if tt:
                ax.hist(tt, bins=20, alpha=0.5, label=algo, color=ALGO_COLORS[i])
    ax.set_xlabel("Travel Time (s)")
    ax.set_ylabel("Frequency")
    ax.set_title("Distribution of Travel Times")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    _save_fig(fig, "hist_travel_time", out_dir)


def fig_cdf_travel_time(data: ExpData, out_dir: Path):
    groups = _group_steps(data)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for i, algo in enumerate(ALGO_ORDER):
        grp = groups.get(algo, [])
        if grp:
            tt = sorted([s.travel_time_s for s in grp if s.travel_time_s > 0])
            if tt:
                cdf = [j / len(tt) for j in range(len(tt))]
                ax.plot(tt, cdf, label=algo, color=ALGO_COLORS[i], linewidth=1.5)
    ax.set_xlabel("Travel Time (s)")
    ax.set_ylabel("Cumulative Probability")
    ax.set_title("CDF of Travel Times")
    ax.legend()
    ax.grid(alpha=0.3)
    _save_fig(fig, "cdf_travel_time", out_dir)


def fig_cdf_speed(data: ExpData, out_dir: Path):
    groups = _group_steps(data)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for i, algo in enumerate(ALGO_ORDER):
        grp = groups.get(algo, [])
        if grp:
            sp = sorted([s.avg_speed_mps for s in grp if s.avg_speed_mps > 0])
            if sp:
                cdf = [j / len(sp) for j in range(len(sp))]
                ax.plot(sp, cdf, label=algo, color=ALGO_COLORS[i], linewidth=1.5)
    ax.set_xlabel("Average Speed (m/s)")
    ax.set_ylabel("Cumulative Probability")
    ax.set_title("CDF of Average Traffic Speeds")
    ax.legend()
    ax.grid(alpha=0.3)
    _save_fig(fig, "cdf_speed", out_dir)


# ---- Scatter ----

def fig_scatter_speed_vs_travel(data: ExpData, out_dir: Path):
    groups = _group_steps(data)
    fig, ax = plt.subplots(figsize=(8, 5))
    for i, algo in enumerate(ALGO_ORDER):
        grp = groups.get(algo, [])
        if grp:
            speeds = [s.avg_speed_mps for s in grp]
            ttimes = [s.travel_time_s for s in grp]
            if any(s > 0 for s in speeds) and any(t > 0 for t in ttimes):
                ax.scatter(speeds, ttimes, label=algo, color=ALGO_COLORS[i], alpha=0.5, s=15)
    ax.set_xlabel("Average Speed (m/s)")
    ax.set_ylabel("Travel Time (s)")
    ax.set_title("Speed vs Travel Time")
    ax.legend()
    ax.grid(alpha=0.3)
    _save_fig(fig, "scatter_speed_vs_travel", out_dir)


# ---- Heatmap ----

def fig_heatmap_congestion(data: ExpData, out_dir: Path):
    groups = _group_steps(data)
    if not groups:
        return
    n_algos = 0
    heatmap_data = []
    labels = []
    for algo in ALGO_ORDER:
        grp = groups.get(algo, [])
        if grp and any(s.congestion_edges > 0 for s in grp):
            heatmap_data.append([s.congestion_edges for s in grp])
            labels.append(algo)
            n_algos += 1
    if n_algos < 2:
        plt.close()
        return
    fig, ax = plt.subplots(figsize=(10, max(3, n_algos * 1.2)))
    im = ax.imshow(heatmap_data, aspect="auto", cmap="YlOrRd", interpolation="nearest")
    ax.set_yticks(range(n_algos))
    ax.set_yticklabels(labels)
    ax.set_xlabel("Simulation Step")
    ax.set_title("Congestion Heatmap Over Time")
    cbar = fig.colorbar(im, ax=ax, shrink=0.6)
    cbar.set_label("Congested Edges")
    _save_fig(fig, "heatmap_congestion", out_dir)


# ---- Dashboards (combined) ----

def fig_dashboard_metrics(data: ExpData, out_dir: Path):
    """3x3 grid of key aggregate metric bars."""
    metrics = _sorted_metrics(data)
    if not metrics:
        return
    names = [m.algorithm for m in metrics]
    bar_specs = [
        ("Travel Time (s)", [m.avg_travel_time_s for m in metrics]),
        ("Execution Time (s)", [m.total_execution_s for m in metrics]),
        ("Memory (MB)", [m.peak_memory_mb for m in metrics]),
        ("Reroutes", [m.total_reroutes for m in metrics]),
        ("Throughput", [m.throughput for m in metrics]),
        ("Avg Speed (m/s)", [m.avg_speed_mps for m in metrics]),
        ("Congestion", [m.max_congestion_edges for m in metrics]),
        ("Teleports", [m.teleport_count for m in metrics]),
        ("Reroute Lat (ms)", [m.avg_rerouting_latency_ms for m in metrics]),
    ]
    fig, axes = plt.subplots(3, 3, figsize=(14, 10))
    for idx, (title, vals) in enumerate(bar_specs):
        row, col = divmod(idx, 3)
        ax = axes[row, col]
        x = range(len(names))
        ax.bar(x, vals, color=ALGO_COLORS[:len(names)], width=0.6, edgecolor="black", linewidth=0.5)
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=30, ha="right", fontsize=7)
        ax.set_title(title, fontsize=9)
        ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    _save_fig(fig, "dashboard_metrics", out_dir)


def fig_dashboard_routing(data: ExpData, out_dir: Path):
    """2x2 grid of offline routing metrics."""
    routing = _sorted_routing(data)
    if not routing:
        return
    names = [r.algorithm for r in routing]
    spec = [
        ("Success Rate (%)", [r.success_rate * 100 for r in routing]),
        ("Avg Runtime (s)", [r.avg_runtime_s for r in routing]),
        ("Avg Distance (m)", [r.avg_distance_m for r in routing]),
        ("Successes", [r.successes for r in routing]),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    for idx, (title, vals) in enumerate(spec):
        row, col = divmod(idx, 2)
        ax = axes[row, col]
        x = range(len(names))
        ax.bar(x, vals, color=ALGO_COLORS[:len(names)], width=0.6, edgecolor="black", linewidth=0.5)
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=30, ha="right", fontsize=8)
        ax.set_title(title, fontsize=10)
        ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    _save_fig(fig, "dashboard_routing", out_dir)


# ---- Summary table ----

def write_summary_table(data: ExpData, out_dir: Path):
    """Write a human-readable summary table as CSV."""
    metrics = _sorted_metrics(data)
    routing = _sorted_routing(data)
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Aggregate metrics table
    path = data_dir / "summary_algorithm_comparison.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Algorithm", "Steps", "Vehicles", "Reroutes", "Emergencies",
                     "MaxCongestion", "MaxBlocked", "AvgTravelTime_s", "AvgSpeed_mps",
                     "Throughput", "Completed", "Failed", "Teleports",
                     "AvgRerouteLat_ms", "Exec_s", "PeakMem_MB"])
        for m in metrics:
            w.writerow([m.algorithm, m.total_steps, m.total_vehicles, m.total_reroutes,
                        m.emergency_events, m.max_congestion_edges, m.max_blocked_edges,
                        f"{m.avg_travel_time_s:.3f}", f"{m.avg_speed_mps:.3f}",
                        m.throughput, m.completed_trips, m.failed_trips,
                        m.teleport_count, f"{m.avg_rerouting_latency_ms:.3f}",
                        f"{m.total_execution_s:.3f}", f"{m.peak_memory_mb:.3f}"])
    print(f"  [TABLE] {path}")

    # Routing benchmark table
    path2 = data_dir / "summary_routing_benchmarks.csv"
    with path2.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Algorithm", "SuccessRate", "AvgRuntime_s", "MaxRuntime_s",
                     "MinRuntime_s", "AvgDistance_m", "Successes", "Failures", "Total"])
        for r in routing:
            w.writerow([r.algorithm, f"{r.success_rate:.3f}", f"{r.avg_runtime_s:.6f}",
                        f"{r.max_runtime_s:.6f}", f"{r.min_runtime_s:.6f}",
                        f"{r.avg_distance_m:.1f}", r.successes, r.failures,
                        r.total_requests])
    print(f"  [TABLE] {path2}")

    # Simulation step summary (max/mean per algorithm)
    groups = _group_steps(data)
    path3 = data_dir / "summary_step_statistics.csv"
    with path3.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Algorithm", "Steps", "MaxActive", "MeanActive", "MaxCongestion",
                     "MeanCongestion", "MaxSpeed", "MeanSpeed", "TotalCompleted",
                     "TotalTeleports"])
        for algo in ALGO_ORDER:
            grp = groups.get(algo, [])
            if grp:
                w.writerow([algo, len(grp),
                            max(s.active_vehicles for s in grp),
                            f"{sum(s.active_vehicles for s in grp) / len(grp):.1f}",
                            max(s.congestion_edges for s in grp),
                            f"{sum(s.congestion_edges for s in grp) / len(grp):.1f}",
                            f"{max(s.avg_speed_mps for s in grp):.3f}",
                            f"{sum(s.avg_speed_mps for s in grp) / len(grp):.3f}",
                            max(s.completed_trips for s in grp),
                            max(s.teleport_count for s in grp)])
    print(f"  [TABLE] {path3}")

    # Processed data for reproducibility
    path4 = data_dir / "processed_metrics.csv"
    with path4.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["algorithm", "metric", "value"])
        for m in metrics:
            for field in ("total_reroutes", "emergency_events", "max_congestion_edges",
                          "max_blocked_edges", "avg_travel_time_s", "avg_speed_mps",
                          "throughput", "completed_trips", "failed_trips",
                          "teleport_count", "avg_rerouting_latency_ms",
                          "total_execution_s", "peak_memory_mb"):
                w.writerow([m.algorithm, field, getattr(m, field, 0)])
    print(f"  [TABLE] {path4}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

_FIGURE_FUNCS = [
    ("Bar: Average Travel Time", fig_bar_travel_time),
    ("Bar: Execution Time", fig_bar_execution_time),
    ("Bar: Memory Usage", fig_bar_memory),
    ("Bar: Total Reroutes", fig_bar_reroutes),
    ("Bar: Throughput", fig_bar_throughput),
    ("Bar: Teleports", fig_bar_teleports),
    ("Bar: Emergency Events", fig_bar_emergency),
    ("Bar: Congestion", fig_bar_congestion),
    ("Bar: Average Speed", fig_bar_speed),
    ("Bar: Reroute Latency", fig_bar_reroute_latency),
    ("Bar: Blocked Edges", fig_bar_blocked),
    ("Bar: Failed Trips", fig_bar_failed_trips),
    ("Bar: Routing Success Rate", fig_bar_routing_success_rate),
    ("Bar: Routing Success/Failure", fig_bar_routing_success),
    ("Bar: Routing Runtime (min/avg/max)", fig_bar_runtime_with_range),
    ("Bar: Routing Distance", fig_bar_routing_distance),
    ("Line: Active Vehicles", fig_line_active_vehicles),
    ("Line: Congestion", fig_line_congestion),
    ("Line: Completed Trips", fig_line_completed),
    ("Line: Teleports", fig_line_teleports),
    ("Line: Average Speed", fig_line_speed),
    ("Line: Travel Time", fig_line_travel_time),
    ("Line: Reroute Latency", fig_line_reroute_latency),
    ("Line: Blocked Edges", fig_line_blocked),
    ("Boxplot: Travel Time", fig_boxplot_travel_time),
    ("Violin: Travel Time", fig_violin_travel_time),
    ("Histogram: Speed", fig_histogram_speed),
    ("Histogram: Travel Time", fig_histogram_travel_time),
    ("CDF: Travel Time", fig_cdf_travel_time),
    ("CDF: Speed", fig_cdf_speed),
    ("Scatter: Speed vs Travel Time", fig_scatter_speed_vs_travel),
    ("Heatmap: Congestion", fig_heatmap_congestion),
    ("Dashboard: Metrics", fig_dashboard_metrics),
    ("Dashboard: Routing", fig_dashboard_routing),
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate all thesis figures from experiment CSVs."
    )
    parser.add_argument("--input", "-i", type=str, default=None,
                        help="Experiment output directory (default: latest)")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Output directory for figures (default: <input>/plots/)")
    parser.add_argument("--list", action="store_true",
                        help="List available experiment runs and exit")
    args = parser.parse_args()

    OUTPUT_ROOT = Path(__file__).resolve().parent.parent / "outputs" / "experiments"

    # List available runs
    if args.list:
        dirs = sorted(OUTPUT_ROOT.iterdir()) if OUTPUT_ROOT.exists() else []
        if not dirs:
            print("No experiment runs found.")
            return 0
        print("Available experiment runs:")
        for d in dirs:
            metrics_present = (d / "metrics_summary.csv").exists()
            print(f"  {d.name}  {'[HAS DATA]' if metrics_present else '[EMPTY]'}")
        return 0

    # Resolve input directory
    if args.input:
        run_dir = Path(args.input)
    else:
        dirs = sorted(OUTPUT_ROOT.iterdir()) if OUTPUT_ROOT.exists() else []
        if not dirs:
            print("ERROR: No experiment runs found. Run an experiment first or use --input.")
            return 1
        run_dir = dirs[-1]

    if not run_dir.exists():
        print(f"ERROR: Input directory not found: {run_dir}")
        return 1

    print(f"Loading experiment: {run_dir}")
    data = load_experiment(run_dir)

    if not data.metrics and not data.steps:
        print("ERROR: No metrics or step data found in experiment directory.")
        return 1

    print(f"  Metrics: {len(data.metrics)} algorithms")
    print(f"  Step log: {len(data.steps)} rows")
    print(f"  Routing log: {len(data.routing)} algorithms")

    # Output directory
    out_dir = Path(args.output) if args.output else (run_dir / "plots")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Initialize matplotlib
    try:
        _init_plt()
    except ImportError:
        print("ERROR: matplotlib is required. Install with: pip install matplotlib")
        return 1

    # Generate all figures
    total = len(_FIGURE_FUNCS)
    pad = len(str(total))
    for idx, (name, func) in enumerate(_FIGURE_FUNCS, 1):
        try:
            print(f"  [{idx:>{pad}}/{total}] {name}", end="")
            func(data, out_dir)
            print("  OK")
        except Exception as e:
            print(f"  SKIP ({e})")

    # Write summary tables
    print(f"\n  Writing summary tables...")
    write_summary_table(data, out_dir)

    # Final report
    print(f"\n{'=' * 60}")
    print(f"  Generated {total} figure groups")
    print(f"  Output: {out_dir}")
    print(f"    PNG:  {out_dir / 'png'}")
    print(f"    PDF:  {out_dir / 'pdf'}")
    print(f"    SVG:  {out_dir / 'svg'}")
    print(f"    Data: {out_dir / 'data'}")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
