#!/usr/bin/env python3
"""Statistical Analysis Framework for E3-Hybrid Thesis Experiment.

Computes:
  - Welch's t-test (unequal variance)
  - Mann-Whitney U test (non-parametric)
  - Cohen's d effect size
  - 95% confidence intervals for all metrics
  - Thesis-ready LaTeX tables
  - Multi-seed aggregation

Usage:
    python scripts/statistical_analysis.py <experiment_dir> [--seeds-dir dir1 dir2 ...]
    python scripts/statistical_analysis.py --multi-seed outputs/experiments/run_* --latex

Output:
    - statistical_report.json       (machine-readable results)
    - statistical_tables.tex        (thesis-ready LaTeX tables)
    - statistical_tables.md         (human-readable markdown tables)
    - convergence_analysis.json     (swarm-specific metrics)
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
import statistics as pystats
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Optional scipy import (graceful fallback if not installed)
# ---------------------------------------------------------------------------
HAS_SCIPY = False
try:
    from scipy.stats import ttest_ind, mannwhitneyu, t as t_dist
    HAS_SCIPY = True
except ImportError:
    pass

# ===================================================================
#  DATA STRUCTURES
# ===================================================================

@dataclass
class AlgorithmMetrics:
    """Aggregated metrics for one algorithm across all seeds."""
    name: str
    edge_congestion_s: list[float] = field(default_factory=list)
    journey_time_s: list[float] = field(default_factory=list)
    avg_speed_mps: list[float] = field(default_factory=list)
    total_reroutes: list[int] = field(default_factory=list)
    throughput: list[int] = field(default_factory=list)
    emergency_events: list[int] = field(default_factory=list)
    teleport_count: list[int] = field(default_factory=list)
    execution_s: list[float] = field(default_factory=list)
    peak_memory_mb: list[float] = field(default_factory=list)
    avg_reroute_latency_ms: list[float] = field(default_factory=list)


@dataclass
class StatisticalResult:
    metric: str
    algo_a: str
    algo_b: str
    mean_a: float
    mean_b: float
    std_a: float
    std_b: float
    welch_t: float | None = None
    welch_p: float | None = None
    mw_u: float | None = None
    mw_p: float | None = None
    cohens_d: float | None = None
    ci95_lower: float | None = None
    ci95_upper: float | None = None
    n_a: int = 0
    n_b: int = 0
    significant: bool | None = None


# ===================================================================
#  STATISTICAL COMPUTATIONS
# ===================================================================

def compute_cohens_d(mean_a: float, mean_b: float, std_a: float, std_b: float,
                     n_a: int, n_b: int) -> float:
    """Cohen's d with pooled standard deviation."""
    num = mean_a - mean_b
    s1 = (n_a - 1) * std_a**2
    s2 = (n_b - 1) * std_b**2
    pooled = math.sqrt((s1 + s2) / (n_a + n_b - 2))
    if abs(pooled) < 1e-15:
        return 0.0
    return num / pooled


def compute_ci95(mean_a: float, std_a: float, n_a: int,
                 mean_b: float, std_b: float, n_b: int) -> tuple[float, float]:
    """95% confidence interval for the difference of means (Welch)."""
    se = math.sqrt(std_a**2 / n_a + std_b**2 / n_b)
    if se < 1e-15:
        return (0.0, 0.0)
    # Welch-Satterthwaite degrees of freedom
    num_df = (std_a**2 / n_a + std_b**2 / n_b)**2
    den_df = (std_a**2 / n_a)**2 / (n_a - 1) + (std_b**2 / n_b)**2 / (n_b - 1)
    df = num_df / den_df if den_df > 0 else min(n_a, n_b) - 1
    diff = mean_a - mean_b
    if HAS_SCIPY:
        t_crit = t_dist.ppf(0.975, df)
    else:
        t_crit = 1.96  # normal approximation
    return (diff - t_crit * se, diff + t_crit * se)


def compare_algorithms(metrics_a: AlgorithmMetrics,
                       metrics_b: AlgorithmMetrics) -> dict[str, StatisticalResult]:
    """Compare two algorithms across all metrics."""
    results: dict[str, StatisticalResult] = {}
    metric_fields = [
        ("edge_congestion_s", "Edge Congestion (s)"),
        ("journey_time_s", "Journey Time (s)"),
        ("avg_speed_mps", "Avg Speed (m/s)"),
        ("total_reroutes", "Total Reroutes"),
        ("throughput", "Throughput"),
        ("emergency_events", "Emergency Events"),
        ("teleport_count", "Teleport Count"),
        ("execution_s", "Execution Time (s)"),
        ("peak_memory_mb", "Peak Memory (MB)"),
        ("avg_reroute_latency_ms", "Reroute Latency (ms)"),
    ]
    for field_name, metric_label in metric_fields:
        va: list[float] = getattr(metrics_a, field_name)
        vb: list[float] = getattr(metrics_b, field_name)
        if len(va) < 2 or len(vb) < 2:
            continue
        mean_a = pystats.mean(va)
        mean_b = pystats.mean(vb)
        std_a = pystats.stdev(va) if len(va) > 1 else 0.0
        std_b = pystats.stdev(vb) if len(vb) > 1 else 0.0
        welch_t = None
        welch_p = None
        mw_u = None
        mw_p = None
        significant = None
        if HAS_SCIPY and len(va) >= 2 and len(vb) >= 2:
            try:
                wt, wp = ttest_ind(va, vb, equal_var=False)
                welch_t, welch_p = float(wt), float(wp)
                mu, mp = mannwhitneyu(va, vb, alternative='two-sided')
                mw_u, mw_p = float(mu), float(mp)
                significant = wp < 0.05
            except Exception:
                pass
        cohens_d = compute_cohens_d(mean_a, mean_b, std_a, std_b, len(va), len(vb))
        ci_low, ci_high = compute_ci95(mean_a, std_a, len(va), mean_b, std_b, len(vb))
        results[field_name] = StatisticalResult(
            metric=metric_label,
            algo_a=metrics_a.name,
            algo_b=metrics_b.name,
            mean_a=round(mean_a, 4),
            mean_b=round(mean_b, 4),
            std_a=round(std_a, 4),
            std_b=round(std_b, 4),
            welch_t=round(welch_t, 4) if welch_t is not None else None,
            welch_p=round(welch_p, 6) if welch_p is not None else None,
            mw_u=round(mw_u, 2) if mw_u is not None else None,
            mw_p=round(mw_p, 6) if mw_p is not None else None,
            cohens_d=round(cohens_d, 4),
            ci95_lower=round(ci_low, 4),
            ci95_upper=round(ci_high, 4),
            n_a=len(va),
            n_b=len(vb),
            significant=significant,
        )
    return results


def load_metrics_csv(path: Path) -> dict[str, AlgorithmMetrics]:
    """Load metrics_summary.csv into per-algorithm containers."""
    algos: dict[str, AlgorithmMetrics] = {}
    if not path.exists():
        return algos
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["algorithm"]
            if name not in algos:
                algos[name] = AlgorithmMetrics(name=name)
            am = algos[name]
            am.edge_congestion_s.append(float(row.get("avg_edge_congestion_s", row.get("avg_travel_time_s", "0"))))
            am.journey_time_s.append(float(row.get("avg_journey_time_s", "0")))
            am.avg_speed_mps.append(float(row.get("avg_speed_mps", 0)))
            am.total_reroutes.append(int(row.get("total_reroutes", 0)))
            am.throughput.append(int(row.get("throughput", 0)))
            am.emergency_events.append(int(row.get("emergency_events", 0)))
            am.teleport_count.append(int(row.get("teleport_count", 0)))
            am.execution_s.append(float(row.get("total_execution_s", 0)))
            am.peak_memory_mb.append(float(row.get("peak_memory_mb", 0)))
            am.avg_reroute_latency_ms.append(float(row.get("avg_rerouting_latency_ms", 0)))
    return algos


def aggregate_across_seeds(seed_dirs: list[Path]) -> dict[str, AlgorithmMetrics]:
    """Aggregate metrics across multiple seed experiment directories."""
    combined: dict[str, AlgorithmMetrics] = {}
    for sd in seed_dirs:
        csv_path = sd / "metrics_summary.csv"
        seed_algos = load_metrics_csv(csv_path)
        for name, am in seed_algos.items():
            if name not in combined:
                combined[name] = AlgorithmMetrics(name=name)
            ca = combined[name]
            ca.edge_congestion_s.extend(am.edge_congestion_s)
            ca.journey_time_s.extend(am.journey_time_s)
            ca.avg_speed_mps.extend(am.avg_speed_mps)
            ca.total_reroutes.extend(am.total_reroutes)
            ca.throughput.extend(am.throughput)
            ca.emergency_events.extend(am.emergency_events)
            ca.teleport_count.extend(am.teleport_count)
            ca.execution_s.extend(am.execution_s)
            ca.peak_memory_mb.extend(am.peak_memory_mb)
            ca.avg_reroute_latency_ms.extend(am.avg_reroute_latency_ms)
    return combined


# ===================================================================
#  TABLE GENERATION
# ===================================================================

def _effect_size_label(d: float) -> str:
    """Interpret Cohen's d magnitude."""
    ad = abs(d)
    if ad < 0.2:
        return "negligible"
    if ad < 0.5:
        return "small"
    if ad < 0.8:
        return "medium"
    return "large"


def generate_latex_table(comparisons: dict[str, dict[str, StatisticalResult]],
                         output_path: Path) -> None:
    """Generate thesis-ready LaTeX table."""
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Statistical Comparison of Routing Algorithms}",
        r"\label{tab:statistical_comparison}",
        r"\begin{tabular}{lrrrrrrr}",
        r"\toprule",
        r"Metric & Algorithm $A$ & Algorithm $B$ & $\mu_A$ & $\mu_B$ & "
        r"$p$ (Welch) & $d$ (Cohen) & 95\% CI \\",
        r"\midrule",
    ]
    row_count = 0
    for algo_pair, results in sorted(comparisons.items()):
        for field_name, sr in sorted(results.items()):
            if row_count > 0:
                lines.append(r"\addlinespace")
            p_str = f"{sr.welch_p:.4f}" if sr.welch_p is not None else "N/A"
            sig = "$\\dagger$" if sr.significant else ""
            d_str = f"{sr.cohens_d:.3f}" if sr.cohens_d is not None else "N/A"
            es = f"({_effect_size_label(sr.cohens_d)})" if sr.cohens_d is not None else ""
            ci_str = (f"[{sr.ci95_lower:.2f}, {sr.ci95_upper:.2f}]"
                      if sr.ci95_lower is not None else "N/A")
            lines.append(
                f"{sr.metric} & {sr.algo_a} & {sr.algo_b} & "
                f"{sr.mean_a:.2f} & {sr.mean_b:.2f} & "
                f"{p_str}{sig} & {d_str} {es} & {ci_str} \\\\"
            )
            row_count += 1
    lines.extend([
        r"\midrule",
        r"\multicolumn{7}{l}{\footnotesize "
        r"$p$ from Welch's t-test (unequal variance); "
        r"$d$ = Cohen's d effect size; "
        r"95\% CI = confidence interval for mean difference; "
        r"$\\dagger p < 0.05$} \\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_markdown_table(comparisons: dict[str, dict[str, StatisticalResult]],
                            output_path: Path) -> None:
    """Generate human-readable markdown table."""
    lines = [
        "# Statistical Comparison of Routing Algorithms",
        "",
        "| Metric | A | B | Mean A | Mean B | p (Welch) | Sig? | d (Cohen) | Effect | 95% CI |",
        "|--------|---|---|--------|--------|-----------|------|-----------|--------|--------|",
    ]
    for algo_pair, results in sorted(comparisons.items()):
        for field_name, sr in sorted(results.items()):
            p_str = f"{sr.welch_p:.4f}" if sr.welch_p is not None else "N/A"
            sig = "Yes" if sr.significant else "No"
            d_str = f"{sr.cohens_d:.3f}" if sr.cohens_d is not None else "N/A"
            es = _effect_size_label(sr.cohens_d) if sr.cohens_d is not None else "N/A"
            ci_str = (f"[{sr.ci95_lower:.2f}, {sr.ci95_upper:.2f}]"
                      if sr.ci95_lower is not None else "N/A")
            lines.append(
                f"| {sr.metric} | {sr.algo_a} | {sr.algo_b} | "
                f"{sr.mean_a:.2f} | {sr.mean_b:.2f} | {p_str} | {sig} | "
                f"{d_str} | {es} | {ci_str} |"
            )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ===================================================================
#  CONVERGENCE ANALYSIS
# ===================================================================

def analyze_convergence(experiment_dir: Path) -> dict[str, Any]:
    """Extract swarm convergence and diversity from algorithm logs."""
    results: dict[str, Any] = {}
    for algo_name in ["aco", "bco", "pso", "e3hybrid"]:
        timing_csv = experiment_dir / "algorithm_timing.csv"
        if timing_csv.exists():
            with timing_csv.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                conv_data = {
                    "convergence_iteration": None,
                    "total_iterations": None,
                    "termination_reason": "unknown",
                }
                # This is a placeholder — real convergence data requires
                # swarm statistics to be exported to the experiment CSV.
                results[algo_name] = conv_data
    return results


# ===================================================================
#  MAIN
# ===================================================================

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Statistical Analysis for E3-Hybrid Thesis Experiment")
    parser.add_argument("experiment_dirs", nargs="+", type=Path,
                        help="One or more experiment output directories")
    parser.add_argument("--multi-seed", action="store_true",
                        help="Treat all dirs as separate seeds and aggregate")
    parser.add_argument("--latex", action="store_true",
                        help="Generate LaTeX tables")
    parser.add_argument("--compare", nargs=2, default=None,
                        help="Compare two specific algorithms only")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Output directory (default: first experiment dir)")
    args = parser.parse_args()

    # Determine output directory
    if args.output_dir:
        out_dir = args.output_dir
    else:
        out_dir = args.experiment_dirs[0]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Print scipy availability
    if not HAS_SCIPY:
        print("[WARN] scipy not installed. Install with: pip install scipy")
        print("[WARN] Falling back to descriptive statistics only (no p-values).")
        print()

    # Load metrics
    if args.multi_seed:
        print(f"Aggregating across {len(args.experiment_dirs)} seed directories...")
        all_algos = aggregate_across_seeds(args.experiment_dirs)
    else:
        csv_path = args.experiment_dirs[0] / "metrics_summary.csv"
        all_algos = load_metrics_csv(csv_path)

    if not all_algos:
        print("[ERROR] No metrics found. Check experiment directory path.")
        return 1

    algo_names = sorted(all_algos.keys())
    print(f"Found algorithms: {', '.join(algo_names)}")
    for name, am in all_algos.items():
        n = len(am.edge_congestion_s)
        print(f"  {name}: {n} data points")
        if n > 0:
            print(f"    Edge congestion: {pystats.mean(am.edge_congestion_s):.2f} ± "
                  f"{pystats.stdev(am.edge_congestion_s) if n > 1 else 0:.2f} s")
            print(f"    Journey time: {pystats.mean(am.journey_time_s):.2f} ± "
                  f"{pystats.stdev(am.journey_time_s) if len(am.journey_time_s) > 1 else 0:.2f} s")
            print(f"    Speed: {pystats.mean(am.avg_speed_mps):.2f} ± "
                  f"{pystats.stdev(am.avg_speed_mps) if n > 1 else 0:.2f} m/s")
            print(f"    Throughput: {pystats.mean(am.throughput):.0f}")

    # Pairwise comparisons
    comparisons: dict[str, dict[str, StatisticalResult]] = {}
    if args.compare:
        a, b = args.compare
        if a in all_algos and b in all_algos:
            key = f"{a}_vs_{b}"
            comparisons[key] = compare_algorithms(all_algos[a], all_algos[b])
    else:
        # Compare E3-Hybrid against every other algorithm
        baseline = "e3hybrid"
        if baseline in all_algos:
            for other in algo_names:
                if other == baseline:
                    continue
                key = f"{baseline}_vs_{other}"
                comparisons[key] = compare_algorithms(all_algos[baseline], all_algos[other])
        # Also compare Dijkstra vs A* (sanity check)
        if "dijkstra" in all_algos and "astar" in all_algos:
            comparisons["dijkstra_vs_astar"] = compare_algorithms(
                all_algos["dijkstra"], all_algos["astar"])

    # Print comparison results
    print()
    print("=" * 72)
    print("  STATISTICAL COMPARISON RESULTS")
    print("=" * 72)
    for pair_name, results in sorted(comparisons.items()):
        print(f"\n  {pair_name}:")
        for field_name, sr in sorted(results.items()):
            sig = " ***" if sr.significant else ""
            p_str = f"p={sr.welch_p:.4f}" if sr.welch_p is not None else "N/A (no scipy)"
            d_es = _effect_size_label(sr.cohens_d) if sr.cohens_d is not None else "N/A"
            print(f"    {sr.metric:<25} {sr.mean_a:<10.2f} vs {sr.mean_b:<10.2f} "
                  f"| d={sr.cohens_d:.3f} ({d_es}) | {p_str}{sig}")

    # Write JSON report
    report: dict[str, Any] = {
        "scipy_available": HAS_SCIPY,
        "algorithms": {
            name: {
                "n": len(am.edge_congestion_s),
                "edge_congestion_mean": round(pystats.mean(am.edge_congestion_s), 4) if am.edge_congestion_s else None,
                "journey_time_mean": round(pystats.mean(am.journey_time_s), 4) if am.journey_time_s else None,
                "speed_mean": round(pystats.mean(am.avg_speed_mps), 4) if am.avg_speed_mps else None,
                "throughput_mean": round(pystats.mean(am.throughput), 2) if am.throughput else None,
                "execution_mean_s": round(pystats.mean(am.execution_s), 4) if am.execution_s else None,
                "memory_mean_mb": round(pystats.mean(am.peak_memory_mb), 4) if am.peak_memory_mb else None,
            }
            for name, am in all_algos.items()
        },
        "comparisons": {
            pair: {fn: asdict(sr) for fn, sr in res.items()}
            for pair, res in comparisons.items()
        },
    }
    json_path = out_dir / "statistical_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[JSON] {json_path}")

    # Generate tables
    md_path = out_dir / "statistical_tables.md"
    generate_markdown_table(comparisons, md_path)
    print(f"[MD]   {md_path}")

    if args.latex:
        tex_path = out_dir / "statistical_tables.tex"
        generate_latex_table(comparisons, tex_path)
        print(f"[TEX]  {tex_path}")

    print()
    if not HAS_SCIPY:
        print("NOTE: scipy not available. Install with: pip install scipy")
        print("Without scipy, p-values and significance tests are not computed.")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
