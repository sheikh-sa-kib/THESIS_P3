"""Research simulator framework for E3-Hybrid EV routing.

The package is organized around clean architecture boundaries so that routing,
decision, communication, metrics, and simulation modules remain independent from
SUMO/TraCI-specific implementation details.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

__all__ = ["__version__"]


def _read_version() -> str:
    """Return the installed package version or the source-tree VERSION value."""

    try:
        return version("e3hybrid")
    except PackageNotFoundError:
        version_path = Path(__file__).resolve().parents[2] / "VERSION"
        return version_path.read_text(encoding="utf-8").strip()


__version__ = _read_version()
