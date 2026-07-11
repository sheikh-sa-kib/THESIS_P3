"""Reproducibility utilities.

The helpers in this module collect run metadata and provide deterministic random
number streams without using Python's module-level random functions directly.
"""

from __future__ import annotations

import hashlib
import json
import platform
import random
import subprocess
import sys
from datetime import UTC, datetime
from dataclasses import asdict, dataclass
from importlib import metadata
from pathlib import Path


@dataclass(frozen=True, slots=True)
class EnvironmentMetadata:
    """Serializable metadata describing the execution environment."""

    python_version: str
    python_executable: str
    operating_system: str
    os_release: str
    architecture: str
    machine: str
    processor: str
    cpu_count: int | None
    installed_packages: dict[str, str]
    git_commit: str | None
    sumo_version: str | None
    timestamp_utc: str
    random_seed: int
    network_sha256: str | None


def collect_environment_metadata(project_root: Path, random_seed: int,
                                 network_file: Path | None = None) -> EnvironmentMetadata:
    """Collect environment metadata for a reproducible run record."""

    if random_seed < 0:
        raise ValueError("random_seed must be non-negative")
    return EnvironmentMetadata(
        python_version=sys.version,
        python_executable=sys.executable,
        operating_system=platform.system(),
        os_release=platform.release(),
        architecture=platform.architecture()[0],
        machine=platform.machine(),
        processor=platform.processor(),
        cpu_count=_read_cpu_count(),
        installed_packages=_read_installed_packages(),
        git_commit=_read_git_commit(project_root),
        sumo_version=None,
        timestamp_utc=datetime.now(UTC).isoformat(),
        random_seed=random_seed,
        network_sha256=_compute_sha256(network_file) if network_file else None,
    )


def write_environment_metadata(metadata: EnvironmentMetadata, path: Path) -> None:
    """Write environment metadata to a JSON file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as metadata_file:
        json.dump(asdict(metadata), metadata_file, indent=2, sort_keys=True)
        metadata_file.write("\n")


class SeededRandomFactory:
    """Factory for deterministic random streams derived from one base seed."""

    def __init__(self, base_seed: int) -> None:
        """Initialize the factory with a non-negative integer base seed."""

        if base_seed < 0:
            raise ValueError("base_seed must be non-negative")
        self._base_seed = base_seed

    def create(self, stream_name: str) -> random.Random:
        """Create a deterministic random generator for a named stream."""

        if not stream_name.strip():
            raise ValueError("stream_name must be non-empty")
        stream_seed = f"{self._base_seed}:{stream_name.strip()}"
        return random.Random(stream_seed)


def _read_git_commit(project_root: Path) -> str | None:
    """Return the current git commit hash if the workspace is a git repository."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    commit = result.stdout.strip()
    return commit or None


def _read_installed_packages() -> dict[str, str]:
    """Return installed Python package names and versions."""

    packages: dict[str, str] = {}
    for distribution in metadata.distributions():
        name = distribution.metadata.get("Name")
        if name:
            packages[name] = distribution.version
    return dict(sorted(packages.items(), key=lambda item: item[0].lower()))


def _read_cpu_count() -> int | None:
    """Return the logical CPU count when the operating system exposes it."""

    try:
        import os

        return os.cpu_count()
    except OSError:
        return None


def _compute_sha256(file_path: Path) -> str | None:
    """Compute SHA-256 checksum of a file for integrity verification."""

    try:
        h = hashlib.sha256()
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, FileNotFoundError):
        return None
