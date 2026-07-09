"""Tests for project version synchronization."""

from pathlib import Path
import tomllib

import e3hybrid


def test_version_file_matches_pyproject_and_package_version() -> None:
    """The VERSION file, pyproject metadata, and package version should match."""

    version_file = Path("VERSION").read_text(encoding="utf-8").strip()
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert version_file == pyproject["project"]["version"]
    assert e3hybrid.__version__ == version_file
