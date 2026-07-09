"""YAML configuration loading.

This module is intentionally small: parsing is delegated to PyYAML, while schema
validation is delegated to typed dataclasses in ``schemas``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from e3hybrid.config.schemas import ProjectConfig, require_mapping
from e3hybrid.core.exceptions import ConfigError


def load_project_config(path: Path) -> ProjectConfig:
    """Load and validate a project configuration from a YAML file."""

    raw_config = load_yaml_mapping(path)
    return ProjectConfig.from_mapping(raw_config)


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    """Load a YAML file and return its top-level mapping."""

    if not path.exists():
        raise ConfigError(f"Configuration file does not exist: {path}")
    if not path.is_file():
        raise ConfigError(f"Configuration path is not a file: {path}")

    try:
        import yaml
    except ModuleNotFoundError as error:
        raise ConfigError(
            "PyYAML is required to load YAML configuration files. "
            "Install project dependencies before running configuration commands."
        ) from error

    with path.open("r", encoding="utf-8") as config_file:
        loaded = yaml.safe_load(config_file)

    if loaded is None:
        raise ConfigError(f"Configuration file is empty: {path}")
    return dict(require_mapping(loaded, "config"))
