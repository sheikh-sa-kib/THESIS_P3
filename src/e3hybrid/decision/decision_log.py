"""DecisionLog — CSV-based immediate logging for every decision.

Design (Decision 4 — approved)
-------------------------------
Decision logging must be enabled for every simulation.
Every decision should be written immediately.
Do not buffer large decision histories in memory.
Use CSV initially.
Future versions may additionally support SQLite or Parquet.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from e3hybrid.decision.decision import Decision


class DecisionLog:
    """CSV-based decision logger with immediate writes.

    Every decision is written immediately upon receipt.  No buffering.
    This ensures decisions are preserved even if the simulation crashes.
    """

    _CSV_HEADERS = [
        "decision_id",
        "vehicle_id",
        "sim_time_s",
        "decision_type",
        "trigger",
        "explanation",
        "winning_policy",
        "applied_policies",
        "veto",
        "confidence",
    ]

    def __init__(self, log_path: Path) -> None:
        """Initialize the decision log.

        Parameters
        ----------
        log_path:
            Path to the CSV file.  Parent directories are created if needed.
        """
        self._log_path = log_path
        self._file_handle: object | None = None
        self._writer: csv.DictWriter | None = None
        self._initialized = False

    def __enter__(self) -> "DecisionLog":
        """Context manager entry — open the log file."""
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._file_handle = self._log_path.open(
            "a", newline="", encoding="utf-8"
        )
        self._writer = csv.DictWriter(
            self._file_handle, fieldnames=self._CSV_HEADERS
        )
        # Write header only if file is empty.
        if self._log_path.stat().st_size == 0:
            self._writer.writeheader()
        self._initialized = True
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Context manager exit — close the log file."""
        if self._file_handle is not None:
            self._file_handle.close()
        self._initialized = False

    def log(self, decision: Decision) -> None:
        """Write a decision to the CSV log immediately.

        Parameters
        ----------
        decision:
            The Decision object to log.

        Raises
        ------
        RuntimeError
            If the log is not initialized (use context manager).
        """
        if not self._initialized or self._writer is None:
            raise RuntimeError(
                "DecisionLog must be used as a context manager "
                "(with DecisionLog(...) as log: ...)"
            )

        row = decision.to_dict()
        self._writer.writerow(row)
        if self._file_handle:
            self._file_handle.flush()

    @classmethod
    def get_log_path(cls, output_dir: Path, run_id: str) -> Path:
        """Generate a standard log path for a simulation run.

        Parameters
        ----------
        output_dir:
            Base output directory for the simulation.
        run_id:
            Unique identifier for the simulation run.

        Returns
        -------
        Path
            Path to the decision log CSV file.
        """
        return output_dir / f"decision_log_{run_id}.csv"
