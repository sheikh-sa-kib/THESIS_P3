"""BenchmarkReporter — writes benchmark artifacts to disk.

Artifact directory structure:

    results/
      <run_timestamp>/
        benchmark_summary.csv
        routing_results.csv
        verification_report.csv
        metadata.json
        configuration_snapshot.yaml

No plots are generated. This is a data-only reporter.
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from e3hybrid.routing.benchmark_config import BenchmarkConfig
    from e3hybrid.routing.benchmark_result import BenchmarkResult


class BenchmarkReporter:
    """Writes benchmark artifacts to disk.

    The reporter produces CSV, JSON, and YAML files with standardized
    schemas for downstream analysis.
    """

    def __init__(self, base_dir: str | Path = "results") -> None:
        """Initialize the reporter.

        Parameters
        ----------
        base_dir:
            Base directory for all benchmark output.
        """
        self._base_dir = Path(base_dir)

    def write_all(
        self,
        results: list[BenchmarkResult],
        config: "BenchmarkConfig",
    ) -> Path:
        """Write all benchmark artifacts.

        Parameters
        ----------
        results:
            List of benchmark results (one per algorithm).
        config:
            The benchmark configuration used.

        Returns
        -------
        Path
            Path to the run output directory.
        """
        run_dir = self._create_run_dir()

        self.write_summary(results, run_dir / "benchmark_summary.csv")
        self.write_routing_results(results, run_dir / "routing_results.csv")
        self.write_verification_report(results, run_dir / "verification_report.csv")
        self.write_metadata(results, config, run_dir / "metadata.json")
        self.write_config_snapshot(config, run_dir / "configuration_snapshot.yaml")

        return run_dir

    def _create_run_dir(self) -> Path:
        """Create a timestamped run directory."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_dir = self._base_dir / f"run_{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    @staticmethod
    def write_summary(
        results: list[BenchmarkResult],
        path: str | Path,
    ) -> None:
        """Write benchmark summary CSV.

        Parameters
        ----------
        results:
            List of benchmark results.
        path:
            Output file path.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "algorithm",
            "scenario",
            "total_requests",
            "successful_requests",
            "failed_requests",
            "avg_runtime_s",
            "max_runtime_s",
            "min_runtime_s",
            "avg_route_distance_m",
            "avg_travel_time_s",
            "avg_total_cost",
            "total_expanded_nodes",
            "avg_expanded_nodes",
            "total_verified",
            "verification_failures",
        ]

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(fieldnames)
            for result in results:
                s = result.summary
                writer.writerow([
                    result.algorithm.name,
                    result.scenario.name,
                    s.total_requests,
                    s.successful_requests,
                    s.failed_requests,
                    f"{s.avg_runtime_s:.6f}",
                    f"{s.max_runtime_s:.6f}",
                    f"{s.min_runtime_s:.6f}",
                    f"{s.avg_route_distance_m:.2f}",
                    f"{s.avg_travel_time_s:.4f}",
                    f"{s.avg_total_cost:.6f}",
                    s.total_expanded_nodes,
                    f"{s.avg_expanded_nodes:.2f}",
                    s.total_verified,
                    s.verification_failures,
                ])

    @staticmethod
    def write_routing_results(
        results: list[BenchmarkResult],
        path: str | Path,
    ) -> None:
        """Write per-request routing results CSV.

        Parameters
        ----------
        results:
            List of benchmark results.
        path:
            Output file path.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "algorithm",
            "scenario",
            "request_index",
            "request_description",
            "success",
            "failure_reason",
            "runtime_s",
            "expanded_nodes",
            "visited_nodes",
            "candidates_generated",
            "route_distance_m",
            "travel_time_s",
            "total_cost",
            "route_valid",
            "memory_bytes",
        ]

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(fieldnames)
            for result in results:
                for i, metrics in enumerate(result.metrics):
                    writer.writerow([
                        result.algorithm.name,
                        result.scenario.name,
                        i,
                        metrics.request_description,
                        metrics.success,
                        metrics.failure_reason or "",
                        f"{metrics.runtime_s:.6f}",
                        metrics.expanded_nodes,
                        metrics.visited_nodes,
                        metrics.candidates_generated,
                        f"{metrics.route_distance_m:.2f}",
                        f"{metrics.travel_time_s:.4f}",
                        f"{metrics.total_cost:.6f}",
                        metrics.route_valid,
                        metrics.memory_bytes,
                    ])

    @staticmethod
    def write_verification_report(
        results: list[BenchmarkResult],
        path: str | Path,
    ) -> None:
        """Write verification report CSV.

        Parameters
        ----------
        results:
            List of benchmark results.
        path:
            Output file path.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "algorithm",
            "scenario",
            "request_index",
            "is_valid",
            "checks_performed",
            "checks_passed",
            "errors",
        ]

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(fieldnames)
            for result in results:
                for i, report in enumerate(result.verification_reports):
                    error_str = "; ".join(
                        f"{e.check_name}: {e.message}" for e in report.errors
                    )
                    writer.writerow([
                        result.algorithm.name,
                        result.scenario.name,
                        i,
                        report.is_valid,
                        report.checks_performed,
                        report.checks_passed,
                        error_str,
                    ])

    @staticmethod
    def write_metadata(
        results: list[BenchmarkResult],
        config: "BenchmarkConfig",
        path: str | Path,
    ) -> None:
        """Write benchmark metadata as JSON.

        Parameters
        ----------
        results:
            List of benchmark results.
        config:
            The benchmark configuration.
        path:
            Output file path.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        metadata: dict[str, Any] = {
            "benchmark_timestamp": datetime.now(timezone.utc).isoformat(),
            "config": _dataclass_to_dict(config),
            "algorithms": [
                {
                    "name": r.algorithm.name,
                    "version": r.algorithm.version,
                    "description": r.algorithm.description,
                    "parameters": r.algorithm.parameters,
                    "scenario": r.scenario.name,
                    "duration_s": r.duration_s,
                    "summary": _dataclass_to_dict(r.summary),
                    "timestamp": r.timestamp,
                }
                for r in results
            ],
            "total_algorithms": len(results),
            "total_scenarios": len({r.scenario.name for r in results}),
        }

        with open(path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)

    @staticmethod
    def write_config_snapshot(
        config: "BenchmarkConfig",
        path: str | Path,
    ) -> None:
        """Write benchmark configuration snapshot as YAML.

        Parameters
        ----------
        config:
            The benchmark configuration.
        path:
            Output file path.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        config_dict = _dataclass_to_dict(config)

        with open(path, "w") as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)


def _dataclass_to_dict(obj: Any) -> Any:
    """Recursively convert a dataclass to a plain dict.

    Handles nested dataclasses, tuples, and sets gracefully.
    """
    if hasattr(obj, "__dataclass_fields__"):
        result: dict[str, Any] = {}
        for field_name in obj.__dataclass_fields__:
            value = getattr(obj, field_name)
            result[field_name] = _dataclass_to_dict(value)
        return result
    if isinstance(obj, tuple):
        return [_dataclass_to_dict(item) for item in obj]
    if isinstance(obj, set):
        return sorted(obj)
    if isinstance(obj, dict):
        return {k: _dataclass_to_dict(v) for k, v in obj.items()}
    return obj
